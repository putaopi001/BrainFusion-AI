import fs from 'node:fs/promises'
import crypto from 'node:crypto'
import assert from 'node:assert/strict'
import { parseNiftiVolume } from '../src/components/mri/niftiGeometry.js'

const [input, output] = process.argv.slice(2)
const reference = JSON.parse(await fs.readFile(input, 'utf8'))
const checked = [], geometryByName = new Map()
for (const record of reference.records) {
  const bytes = await fs.readFile(record.path)
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
  const geometry = parseNiftiVolume(buffer, { labelmap: record.labelmap, referenceGeometry: record.labelmap ? geometryByName.get('t2f') : null })
  geometryByName.set(record.name, geometry)
  assert.deepEqual(geometry.dimensions, record.shape)
  assert.equal(crypto.createHash('sha256').update(geometry.scalarData).digest('hex'), record.voxel_sha256)
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), record.raw_sha256)
  for (const p of record.points) {
    const world = geometry.origin.map((v, j) => v + p.ijk.reduce((s, index, axis) => s + index * geometry.spacing[axis] * geometry.direction[axis * 3 + j], 0))
    world.forEach((v, j) => assert.ok(Math.abs(v - p.lps[j]) < 1e-5))
    const index = p.ijk[0] + geometry.dimensions[0] * (p.ijk[1] + geometry.dimensions[1] * p.ijk[2])
    assert.equal(geometry.scalarData[index], p.value)
  }
  if (record.labelmap) {
    assert.throws(() => parseNiftiVolume(buffer, { labelmap: true, referenceGeometry: { ...geometry, origin: geometry.origin.map(v => v + 1) } }), /空间不一致/)
  }
  checked.push({ name: record.name, voxelCount: geometry.scalarData.length, checks: 'every voxel SHA; independent nibabel world coordinates; original bytes unchanged' })
}
await fs.writeFile(output, JSON.stringify({ status: 'passed', checked }, null, 2), { flag: 'wx' })
