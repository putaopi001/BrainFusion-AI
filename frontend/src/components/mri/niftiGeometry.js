import * as nifti from 'nifti-reader-js'

// NIfTI stores x fastest and uses RAS mm; Cornerstone uses LPS mm.
// Preserve voxel order. No reorientation, interpolation or registration.
export function parseNiftiVolume(buffer, { labelmap = false, referenceGeometry = null } = {}) {
  if (nifti.isCompressed(buffer)) buffer = nifti.decompress(buffer)
  if (!nifti.isNIFTI(buffer)) throw Error('不是受支持的 NIfTI 文件')
  const h = nifti.readHeader(buffer)
  if (h.dims[0] < 3 || h.dims.slice(4, h.dims[0] + 1).some(n => n > 1)) throw Error('仅支持单个三维体数据')
  const units = h.xyzt_units & 7
  // Existing model masks omit units. Accept only with an explicit mm MRI
  // reference and exactly matching geometry; never change the original mask.
  if (units !== 2 && !(units === 0 && labelmap && referenceGeometry)) throw Error('NIfTI 必须明确使用毫米单位')
  if (!(h.sform_code > 0 || h.qform_code > 0)) throw Error('NIfTI 缺少有效空间变换')
  const dimensions = h.dims.slice(1, 4)
  let a = h.affine
  // Match nibabel: a valid sform takes precedence, irrespective of code rank.
  if (h.sform_code > 0) {
    const header = new DataView(buffer), isV2 = nifti.isNIFTI2(buffer)
    const start = isV2 ? 400 : 280, size = isV2 ? 8 : 4
    a = [0, 1, 2].map(i => [0, 1, 2, 3].map(j => header[isV2 ? 'getFloat64' : 'getFloat32'](start + (i * 4 + j) * size, h.littleEndian)))
  }
  const origin = [-a[0][3], -a[1][3], a[2][3]]
  const columns = [0, 1, 2].map(j => [-a[0][j], -a[1][j], a[2][j]])
  const spacing = columns.map(c => Math.hypot(...c))
  if ([...origin, ...spacing].some(n => !Number.isFinite(n)) || spacing.some(n => n <= 0)) throw Error('无效的 NIfTI 空间变换')
  const axes = columns.map((c, i) => c.map(n => n / spacing[i]))
  for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) {
    if (Math.abs(axes[i].reduce((s, n, k) => s + n * axes[j][k], 0)) > 1e-5) throw Error('不支持剪切空间，不自动重采样')
  }
  const types = { 2: ['getUint8', 1], 4: ['getInt16', 2], 8: ['getInt32', 4], 16: ['getFloat32', 4], 64: ['getFloat64', 8], 256: ['getInt8', 1], 512: ['getUint16', 2], 768: ['getUint32', 4] }
  const type = types[h.datatypeCode]
  if (!type) throw Error('不支持的 NIfTI 数据类型：' + h.datatypeCode)
  const count = dimensions.reduce((a, b) => a * b, 1)
  const data = new DataView(nifti.readImage(h, buffer))
  if (data.byteLength !== count * type[1]) throw Error('NIfTI 体素长度不匹配')
  const slope = Number.isFinite(h.scl_slope) && h.scl_slope !== 0 ? h.scl_slope : 1
  const intercept = Number.isFinite(h.scl_slope) && h.scl_slope !== 0 && Number.isFinite(h.scl_inter) ? h.scl_inter : 0
  const scalarData = labelmap ? new Uint8Array(count) : new Float32Array(count)
  for (let i = 0; i < count; i++) {
    const value = data[type[0]](i * type[1], h.littleEndian) * slope + intercept
    if (!Number.isFinite(value)) throw Error('NIfTI 包含非有限体素')
    if (labelmap && (!Number.isInteger(value) || value < 0 || value > 3)) throw Error('掩膜标签必须为 0/1/2/3')
    scalarData[i] = value
  }
  const result = { dimensions, origin, spacing, direction: axes.flat(), scalarData }
  if (referenceGeometry && !sameGeometry(referenceGeometry, result)) throw Error('掩膜与毫米参考空间不一致')
  return result
}

export function sameGeometry(a, b) {
  return ['dimensions', 'origin', 'spacing', 'direction'].every(key => a[key].length === b[key].length && a[key].every((v, i) => Math.abs(v - b[key][i]) < 1e-4))
}
