import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {makePolygon} from './stack-model.js';
export function createStack(host, geometry, onSelect) {
  const renderer = new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
  renderer.domElement.setAttribute('aria-label','3D planar geometry. Drag to orbit, scroll to zoom; equivalent view buttons and object table are available.');
  renderer.domElement.setAttribute('role','img');
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38,1,0.1,100000);
  camera.up.set(0,0,1);
  const controls = new OrbitControls(camera,renderer.domElement);
  controls.enableDamping = false; controls.autoRotate = false;
  const box=geometry.bbox_um;
  const center=new THREE.Vector3((box.xmin+box.xmax)/2,(box.ymin+box.ymax)/2,0);
  const extent=Math.max(box.width,box.height,1);
  controls.target.copy(center); controls.minDistance=extent/10; controls.maxDistance=extent*20;
  const meshes=geometry.polygons.map((p,i)=>{const mesh=makePolygon(p);mesh.userData.index=i;scene.add(mesh);return mesh;});
  let selection=0; let disposed=false;
  const theme=matchMedia('(prefers-color-scheme: dark)');
  function render(){if(!disposed)renderer.render(scene,camera);}
  function paint(){
    const css=getComputedStyle(document.documentElement);
    scene.background=new THREE.Color(css.getPropertyValue('--soft').trim());
    meshes.forEach((m,i)=>m.material.color.set(css.getPropertyValue(i===selection?'--action':'--secondary').trim()));
    render();
  }
  function frame(top=false){
    controls.target.copy(center);
    const distance=extent/(2*Math.tan(THREE.MathUtils.degToRad(camera.fov/2)))*Math.max(1,1/camera.aspect)*1.2;
    camera.position.copy(center).add(new THREE.Vector3(top?0.001:distance*.65,top?0: -distance*.45,top?distance:distance*.7));
    controls.update();render();
  }
  function resize(){const width=host.clientWidth;if(!width)return;renderer.setSize(width,360,false);camera.aspect=width/360;camera.updateProjectionMatrix();render();}
  const observer=new ResizeObserver(resize);observer.observe(host);
  controls.addEventListener('change',render); theme.addEventListener('change',paint);
  let start;
  function down(event){start=[event.clientX,event.clientY];}
  function up(event){
    if(!start||Math.hypot(event.clientX-start[0],event.clientY-start[1])>5)return;
    const rect=renderer.domElement.getBoundingClientRect();
    const pointer=new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
    const ray=new THREE.Raycaster();ray.setFromCamera(pointer,camera);
    const hit=ray.intersectObjects(meshes)[0];if(hit)onSelect(hit.object.userData.index);
  }
  renderer.domElement.addEventListener('pointerdown',down);renderer.domElement.addEventListener('pointerup',up);
  function lost(event){event.preventDefault();document.getElementById('stack-status').textContent='3D graphics context lost. Reload to retry; retained 2D geometry and evidence remain available.';}
  renderer.domElement.addEventListener('webglcontextlost',lost);
  resize();frame();paint();
  return {
    select(index){selection=index;paint();},
    command(name){
      if(name==='reset'||name==='top'){frame(name==='top');return;}
      const offset=camera.position.clone().sub(controls.target);
      if(name==='left'||name==='right')offset.applyAxisAngle(new THREE.Vector3(0,0,1),name==='left'?.25:-.25);
      else offset.multiplyScalar(name==='in'?.8:1.25);
      offset.clampLength(controls.minDistance,controls.maxDistance);
      camera.position.copy(controls.target).add(offset);controls.update();render();
    },
    dispose(){disposed=true;observer.disconnect();theme.removeEventListener('change',paint);controls.dispose();meshes.forEach(m=>{m.geometry.dispose();m.material.dispose();});renderer.dispose();renderer.domElement.remove();}
  };
}
