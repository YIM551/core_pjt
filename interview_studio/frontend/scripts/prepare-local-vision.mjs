// Explicit setup only: runtime uses same-origin assets and never these external URLs.
import {mkdir,readFile,writeFile,copyFile,readdir} from 'node:fs/promises'
import {createHash} from 'node:crypto'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
const root=fileURLToPath(new URL('../',import.meta.url))
const manifest=[
 {name:'face_landmarker.task',url:'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',sha256:'64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'},
 {name:'pose_landmarker_lite.task',url:'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',sha256:'59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a'}
]
const hash=data=>createHash('sha256').update(data).digest('hex')
await mkdir(path.join(root,'public/models'),{recursive:true})
await mkdir(path.join(root,'public/mediapipe/wasm'),{recursive:true})
for(const item of manifest){
 const destination=path.join(root,'public/models',item.name)
 let data;try{data=await readFile(destination)}catch{}
 if(!data||hash(data)!==item.sha256){const response=await fetch(item.url,{signal:AbortSignal.timeout(120000)});if(!response.ok)throw new Error(`Model download failed: ${response.status}`);data=Buffer.from(await response.arrayBuffer());if(hash(data)!==item.sha256)throw new Error(`SHA256 mismatch: ${item.name}`);await writeFile(destination,data)}
 console.log(`Verified ${item.name}: ${item.sha256}`)
}
const wasm=path.join(root,'node_modules/@mediapipe/tasks-vision/wasm')
for(const name of await readdir(wasm))if(/\.(js|wasm)$/.test(name))await copyFile(path.join(wasm,name),path.join(root,'public/mediapipe/wasm',name))
console.log('Local vision assets ready. Runtime needs no external model connection.')
