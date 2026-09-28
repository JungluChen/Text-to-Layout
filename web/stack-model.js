import {Shape,ShapeGeometry,Mesh,MeshBasicMaterial,DoubleSide} from 'three';
// Display the retained x/y coordinates at z=0. No thickness or material inference.
export function makePolygon(polygon) {
  if (!Array.isArray(polygon.points) || polygon.points.length < 3 ||
      polygon.points.some(p => p.length !== 2 || !p.every(Number.isFinite))) {
    throw new Error('Invalid retained polygon coordinates');
  }
  const shape = new Shape();
  polygon.points.forEach(([x,y],i) => i ? shape.lineTo(x,y) : shape.moveTo(x,y));
  shape.closePath();
  return new Mesh(new ShapeGeometry(shape), new MeshBasicMaterial({color:0x4d5b68,side:DoubleSide}));
}
