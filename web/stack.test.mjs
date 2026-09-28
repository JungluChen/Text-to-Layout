import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {makePolygon} from './stack-model.js';
const geometry=JSON.parse(readFileSync(new URL('./assets/output.json',import.meta.url)));
test('3D display preserves retained polygon bounds and does not invent thickness',()=>{
 for(const polygon of geometry.polygons){
  const mesh=makePolygon(polygon);mesh.geometry.computeBoundingBox();const b=mesh.geometry.boundingBox;
  assert.equal(b.min.x,Math.min(...polygon.points.map(p=>p[0])));
  assert.equal(b.max.y,Math.max(...polygon.points.map(p=>p[1])));
  assert.equal(b.min.z,0);assert.equal(b.max.z,0);
  mesh.geometry.dispose();mesh.material.dispose();
 }
});
test('non-finite and incomplete polygons are rejected',()=>{
 assert.throws(()=>makePolygon({points:[[0,0],[1,NaN],[1,1]]}));
 assert.throws(()=>makePolygon({points:[[0,0],[1,1]]}));
});
