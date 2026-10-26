import { cache, imageLoader, volumeLoader } from '@cornerstonejs/core'
import { init as initDicom, wadors } from '@cornerstonejs/dicom-image-loader'

const sessions = new Map()
let initialized = false
const uid = /^(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+$/
const hash = /^[0-9a-f]{64}$/

function initialize() {
  if (initialized) return
  initDicom({ maxWebWorkers: 1, beforeSend(xhr, imageId) {
    const session = sessions.get(imageId)
    xhr.timeout = 30000
    if (!session || session.closed) { setTimeout(() => xhr.abort(), 0); return {} }
    session.requests.add(xhr)
    const abort = () => xhr.abort()
    session.signal.addEventListener('abort', abort, { once: true })
    xhr.addEventListener('loadend', () => {
      session.requests.delete(xhr)
      session.signal.removeEventListener('abort', abort)
      if (xhr.status && xhr.status !== 200) {
        session.failure = 'DICOM 帧读取失败（HTTP ' + xhr.status + '），请重新打开序列。'
        try {
          const detail = JSON.parse(new TextDecoder().decode(xhr.response)).detail
          if (typeof detail?.message === 'string') session.failure = detail.message
        } catch { /* Only safe server detail is shown, never an upstream body. */ }
      }
    }, { once: true })
    return {}
  } })
  // 5.7 loadAndCacheImage ignores the cache insertion promise. Handle that
  // promise for our owned images, while retaining the rejected pixel promise
  // so the volume and visible error still fail normally. No global error filter.
  // This owned prefix has the same 7-character scheme length as "wadors:".
  imageLoader.registerImageLoader('bfwado', (imageId, options) => {
    const object = wadors.loadImage(imageId, options)
    if (!cache.getImageLoadObject(imageId)) cache.putImageLoadObject(imageId, object).catch(() => {})
    return object
  })
  initialized = true
}

export function dicomImageIds(manifest, { caseId, archiveOnly = false, studyUid, seriesUid, baseURL, sessionId }) {
  const sourceMatches = archiveOnly
    ? manifest.archive_only === true && manifest.source_case_id == null && caseId == null
    : manifest.archive_only !== true && manifest.source_case_id === caseId
  if (manifest.format !== 'dicom-series-view-manifest-v1' || !sourceMatches
      || manifest.study_uid !== studyUid || manifest.series_uid !== seriesUid
      || !manifest.transport_enabled || !manifest.pixel_read_enabled || !manifest.archive_server_identity_pinned
      || !hash.test(manifest.metadata_sha256) || !hash.test(manifest.archive_fingerprint)
      || !Array.isArray(manifest.instances) || manifest.instances.length !== manifest.instance_count
      || manifest.instance_count < 2 || manifest.instance_count > 512) {
    throw Error('DICOM 来源、病例关联或像素读取契约不完整。')
  }
  const base = new URL((baseURL || '').replace(/\/$/, '') + '/', window.location.href)
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
    throw Error('DICOM API 地址无效。')
  }
  const seen = new Set()
  return manifest.instances.map(row => {
    if (!uid.test(row.instance_uid) || row.instance_uid.length > 64 || seen.has(row.instance_uid)
        || !hash.test(row.metadata_sha256)) throw Error('DICOM 实例身份或版本无效。')
    seen.add(row.instance_uid)
    const expected = archiveOnly
      ? '/pacs/archive/studies/' + studyUid + '/series/' + seriesUid + '/instances/' + row.instance_uid + '/frames/1'
      : '/pacs/cases/' + caseId + '/studies/' + studyUid + '/series/' + seriesUid
        + '/instances/' + row.instance_uid + '/frames/1'
    const bulk = row.metadata?.['7FE00010']?.BulkDataURI
    const uri = new URL(bulk, base)
    if (typeof bulk !== 'string' || !bulk.startsWith(expected + '?') || uri.pathname !== expected
        || uri.searchParams.get('metadata_sha256') !== row.metadata_sha256
        || uri.searchParams.get('archive_fingerprint') !== manifest.archive_fingerprint
        || uri.hash || [...uri.searchParams.keys()].length !== 2
        || row.metadata['00080018']?.Value?.[0] !== row.instance_uid
        || row.metadata['0020000D']?.Value?.[0] !== studyUid
        || row.metadata['0020000E']?.Value?.[0] !== seriesUid) {
      throw Error('DICOM 帧地址与来源版本不一致，已拒绝读取。')
    }
    // Keep any deployment API prefix, while refusing external BulkDataURI.
    const endpoint = new URL(base.href.replace(/\/$/, '') + bulk)
    endpoint.searchParams.set('bf_session', sessionId)
    return 'bfwado:' + endpoint.href
  })
}

export function createDicomSession(signal) {
  initialize()
  const session = { signal, requests: new Set(), imageIds: [], volume: null, closed: false, failure: '' }
  const clearImage = imageId => {
    if (cache.getImageLoadObject(imageId)) cache.removeImageLoadObject(imageId)
    wadors.metaDataManager.remove(imageId)
    sessions.delete(imageId)
  }
  const dispose = () => {
    if (session.closed) return
    session.closed = true
    session.volume?.cancelLoading()
    session.requests.forEach(xhr => xhr.abort())
    session.requests.clear()
    if (session.volume && cache.getVolumeLoadObject(session.volume.volumeId)) cache.removeVolumeLoadObject(session.volume.volumeId)
    session.imageIds.forEach(imageId => {
      const pending = cache.getImageLoadObject(imageId)?.promise
      if (pending) pending.finally(() => clearImage(imageId)).catch(() => {})
      clearImage(imageId)
    })
    signal.removeEventListener('abort', dispose)
  }
  signal.addEventListener('abort', dispose, { once: true })
  return { dispose, async load(manifest, options) {
    if (signal.aborted || session.closed) throw Error('DICOM 阅片器已关闭。')
    const imageIds = dicomImageIds(manifest, options)
    session.imageIds = imageIds
    imageIds.forEach((imageId, index) => {
      sessions.set(imageId, session)
      wadors.metaDataManager.add(imageId, structuredClone(manifest.instances[index].metadata))
    })
    const volume = await volumeLoader.createAndCacheVolume(options.volumeId, { imageIds })
    session.volume = volume
    if (signal.aborted || session.closed) {
      if (cache.getVolumeLoadObject(volume.volumeId)) cache.removeVolumeLoadObject(volume.volumeId)
      throw Error('DICOM 阅片器已关闭。')
    }
    const dims = manifest.geometry.dimensions
    if (volume.dimensions.some((v,i) => v !== dims[i])) throw Error('Cornerstone DICOM 矩阵与源元数据不一致。')
    // Check actual toolkit affine against each retained DICOM plane.
    volume.imageIds.forEach((imageId,k) => {
      const original = wadors.metaDataManager.get(imageId)['00200032'].Value.map(Number)
      const world = volume.imageData.indexToWorld([0,0,k])
      if (world.some((v,i) => Math.abs(v-original[i]) > 0.002)) {
        throw Error('Cornerstone DICOM 空间与患者层位不一致，已拒绝显示。')
      }
    })
    await new Promise((resolve,reject) => {
      const finish = error => {
        clearTimeout(timer); signal.removeEventListener('abort', abort)
        error ? reject(error) : resolve()
      }
      const abort = () => finish(Error('DICOM 加载已取消。'))
      const timer = setTimeout(() => finish(Error('DICOM 全序列像素加载超时。')),60000)
      signal.addEventListener('abort',abort,{once:true})
      volume.load(event => {
        if (!event.success || event.framesLoaded !== imageIds.length) {
          finish(Error(session.failure || 'DICOM 帧未完整加载，拒绝显示不完整序列。'))
        } else finish()
      })
    })
    if (signal.aborted || session.closed) throw Error('DICOM 加载已取消。')
    return volume
  } }
}
