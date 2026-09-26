// Offline sprite generator. See frontend/src/assets/vehicles/README.md.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('../frontend/node_modules/@playwright/test');
const assetRoot = path.resolve(__dirname, '../frontend/src/assets/vehicles');
const toolRoot = path.resolve(process.argv[2] || '/tmp/vehicle-render-tools');
const html = "<script type=\"importmap\">{\"imports\":{\"three\":\"/node_modules/three/build/three.module.js\",\"three/addons/\":\"/node_modules/three/examples/jsm/\"}}</script>\n<script type=\"module\">\nimport * as T from 'three';\nimport {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';\nimport {FBXLoader} from 'three/addons/loaders/FBXLoader.js';\nconst r=new T.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});r.setSize(128,128);r.setClearColor(0,0);r.outputColorSpace=T.SRGBColorSpace;\nconst scene=new T.Scene();scene.add(new T.HemisphereLight(0xffffff,0x657180,1.5));const light=new T.DirectionalLight(0xffffff,2);light.position.set(-3,7,5);scene.add(light);\nconst camera=new T.OrthographicCamera(-1.8,1.8,1.8,-1.8,.1,100);camera.position.set(0,6,8);camera.lookAt(0,0,0);\nwindow.renderVehicle=async(type,risk)=>{\nconst paint={LOW:0x35a976,MEDIUM:0xe9bc36,HIGH:0xed7831,CRITICAL:0xd93e51,UNKNOWN:0x8b98a3}[risk];\nlet model;if(type==='unknown'){\nmodel=new T.Group();\nconst body=new T.MeshStandardMaterial({color:paint,roughness:.85});\nconst dark=new T.MeshStandardMaterial({color:0x34414d,roughness:1});\nconst shell=new T.Mesh(new T.BoxGeometry(1.15,.65,2.05),body);shell.position.y=.65;model.add(shell);\nconst roof=new T.Mesh(new T.BoxGeometry(.96,.25,1.55),body);roof.position.y=1.08;model.add(roof);\nfor(const x of [-.59,.59])for(const z of [-.63,.63]){const wheel=new T.Mesh(new T.CylinderGeometry(.26,.26,.16,12),dark);wheel.rotation.z=Math.PI/2;wheel.position.set(x,.26,z);model.add(wheel);}\n}else if(type==='bus'){model=await new FBXLoader().loadAsync('/sources/Bus.fbx');}else model=(await new GLTFLoader().loadAsync('/sources/'+type+'.glb')).scene;\nif(type==='bus')model.rotation.y=Math.PI/2;\nconst box=new T.Box3().setFromObject(model),size=box.getSize(new T.Vector3()),center=box.getCenter(new T.Vector3());model.position.sub(center);const group=new T.Group();group.add(model);group.scale.setScalar(2.7/Math.max(size.x,size.y,size.z));scene.add(group);\nif(type==='bus'){const colors={Bottom:0x283441,Bumper:0x465566,Details:paint,Lights:0xfff4c2,Material:paint,Windows:0x40677f,Wheels:0x202a35};model.traverse(o=>{if(o.isMesh){for(const mat of (Array.isArray(o.material)?o.material:[o.material])){mat.color.setHex(colors[mat.name]??paint);mat.shininess=12;}}});}\nif(['car','van','truck'].includes(type)){\n  const bodyColumn={car:13,van:15,truck:7}[type];\n  const textures=new Map();\n  model.traverse(o=>{if(!o.isMesh)return;\n    o.material=o.material.clone();const original=o.material.map;if(!original)return;\n    if(!textures.has(original)){\n      const canvas=document.createElement('canvas');canvas.width=original.image.width;canvas.height=original.image.height;\n      const ctx=canvas.getContext('2d');ctx.drawImage(original.image,0,0);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);\n      for(let i=0;i<pixels.data.length;i+=4){const x=(i/4)%canvas.width,y=Math.floor(i/4/canvas.width);if(Math.floor(x/32)===bodyColumn && Math.floor(y/128)===1){const shade=.75+.25*Math.max(pixels.data[i],pixels.data[i+1],pixels.data[i+2])/255;pixels.data[i]=((paint>>16)&255)*shade;pixels.data[i+1]=((paint>>8)&255)*shade;pixels.data[i+2]=(paint&255)*shade;}}\n      ctx.putImageData(pixels,0,0);const texture=original.clone();texture.image=canvas;texture.needsUpdate=true;textures.set(original,texture);\n    }o.material.map=textures.get(original);\n  });\n}\nconst images=[];for(let i=0;i<8;i++){group.rotation.y=Math.PI+i*-Math.PI/4;r.render(scene,camera);images.push(r.domElement.toDataURL('image/webp',.95));}scene.remove(group);return {images,size:size.toArray()};};\n</script>\n";
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/') { res.setHeader('Content-Type', 'text/html'); res.end(html); return; }
  const source = url.pathname.startsWith('/sources/');
  const root = source ? assetRoot : toolRoot;
  const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
  const types = { '.js':'text/javascript', '.png':'image/png', '.glb':'model/gltf-binary' };
  res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => window.renderVehicle);
    for (const type of ['car', 'van', 'truck', 'bus', 'unknown']) {
      for (const risk of ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN']) {
      const { images } = await page.evaluate(({type,risk}) => window.renderVehicle(type,risk), {type,risk});
      images.forEach((data, index) => fs.writeFileSync(path.join(assetRoot, `${type}-${risk}-${index}.webp`), Buffer.from(data.split(',')[1], 'base64')));
      console.log(`Rendered ${type} ${risk}: eight headings`);
      }
    }
  } finally { if (browser) await browser.close(); server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
