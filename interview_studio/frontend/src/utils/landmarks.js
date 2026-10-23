export function direction(face) {
  if (!face?.[1] || !face?.[33] || !face?.[263]) return null
  const left=face[33],right=face[263],nose=face[1]
  const width=Math.hypot(left.x-right.x,left.y-right.y)
  return width>.01 ? {x:(nose.x-(left.x+right.x)/2)/width,y:(nose.y-(left.y+right.y)/2)/width} : null
}
export function wristMovement(pose,previous) {
  if(!pose||!previous)return null
  const indices=[11,12,15,16]
  if(indices.some(i=>!pose[i]||!previous[i]||(pose[i].visibility??0)<.6||(previous[i].visibility??0)<.6))return null
  const width=Math.hypot(pose[11].x-pose[12].x,pose[11].y-pose[12].y)
  if(width<.03)return null
  return (Math.hypot(pose[15].x-previous[15].x,pose[15].y-previous[15].y)+Math.hypot(pose[16].x-previous[16].x,pose[16].y-previous[16].y))/(2*width)
}
export function sampleLandmarks(face,pose,previous,baseline,t_ms){
  const current=direction(face)
  return {t_ms,face_valid:!!current,pose_valid:!!pose?.length,camera_direction_deviation:current&&baseline?Math.hypot(current.x-baseline.x,current.y-baseline.y):null,normalized_wrist_movement:wristMovement(pose,previous)}
}

// Iris positions use both eyes' local axes; closed/occluded eyes are unobservable.
export function irisObservation(face) {
  if (!face || face.length < 478) return null
  const eye = (a,b,top,bottom,iris) => {
    const p=face[a], q=face[b], t=face[top], d=face[bottom], i=face[iris]
    if (![p,q,t,d,i].every(v=>v&&Number.isFinite(v.x)&&Number.isFinite(v.y))) return null
    const dx=q.x-p.x,dy=q.y-p.y,w=Math.hypot(dx,dy),opening=Math.hypot(t.x-d.x,t.y-d.y)
    if(w<.015 || opening/w<.12)return null
    return {x:((i.x-p.x)*dx+(i.y-p.y)*dy)/(w*w),y:((i.x-(p.x+q.x)/2)*-dy+(i.y-(p.y+q.y)/2)*dx)/(w*w)}
  }
  const l=eye(33,133,159,145,468),r=eye(362,263,386,374,473),head=direction(face)
  if(!l||!r||!head || Math.abs(l.x-r.x)>.3 || Math.abs(l.y-r.y)>.25)return null
  return {x:(l.x+r.x)/2,y:(l.y+r.y)/2,head}
}
function solve(matrix, vector) {
  const a=matrix.map((row,i)=>[...row,vector[i]])
  for(let c=0;c<3;c++){
    let pivot=c;for(let r=c+1;r<3;r++)if(Math.abs(a[r][c])>Math.abs(a[pivot][c]))pivot=r
    if(Math.abs(a[pivot][c])<1e-8)throw new Error('눈동자 변화가 충분하지 않습니다. 보정을 다시 진행하세요.')
    ;[a[c],a[pivot]]=[a[pivot],a[c]]
    const v=a[c][c];for(let j=c;j<4;j++)a[c][j]/=v
    for(let r=0;r<3;r++)if(r!==c){const k=a[r][c];for(let j=c;j<4;j++)a[r][j]-=k*a[c][j]}
  }
  return a.map(row=>row[3])
}
const mean=rows=>({x:rows.reduce((s,r)=>s+r.x,0)/rows.length,y:rows.reduce((s,r)=>s+r.y,0)/rows.length,head:{x:rows.reduce((s,r)=>s+r.head.x,0)/rows.length,y:rows.reduce((s,r)=>s+r.head.y,0)/rows.length}})
export function fitIrisCalibration(points,camera) {
  if(points.length!==5||points.some(p=>p.samples.length<20)||camera.length<20)throw new Error('각 지점에서 유효한 눈동자 관찰 20개가 필요합니다.')
  const all=[...points.flatMap(p=>p.samples),...camera],headCenter=mean(all).head
  if(all.some(p=>Math.hypot(p.head.x-headCenter.x,p.head.y-headCenter.y)>.15))throw new Error('보정 중 고개가 움직였습니다. 고개를 고정하고 다시 진행하세요.')
  const train=points.map(p=>({...mean(p.samples.filter((_,i)=>i%2===0)),target:p.target}))
  const matrix=Array.from({length:3},()=>[0,0,0]),bx=[0,0,0],by=[0,0,0]
  for(const p of train){const row=[1,p.x,p.y];for(let i=0;i<3;i++){bx[i]+=row[i]*p.target.x;by[i]+=row[i]*p.target.y;for(let j=0;j<3;j++)matrix[i][j]+=row[i]*row[j]}}
  const cx=solve(matrix,bx),cy=solve(matrix,by)
  const project=p=>({x:cx[0]+cx[1]*p.x+cx[2]*p.y,y:cy[0]+cy[1]*p.x+cy[2]*p.y})
  const validation_error=Math.sqrt(points.reduce((sum,p)=>{const projected=project(mean(p.samples.filter((_,i)=>i%2===1)));return sum+(projected.x-p.target.x)**2+(projected.y-p.target.y)**2},0)/5)
  if(!Number.isFinite(validation_error)||validation_error>.25)throw new Error('보정 오차가 커 시선은 미측정입니다. 조명·안경 반사·거리 확인 후 다시 진행하세요.')
  const baseline=mean(camera),cameraPoint=project(baseline)
  return {cx,cy,baseline:baseline.head,cameraPoint,validation_error,point_count:6}
}
export function calibratedGaze(observation,calibration){
  if(!observation||!calibration)return {gaze_x:null,gaze_y:null,gaze_region:'unknown',camera_direction_deviation:null,quality_reason:calibration?'iris_unobservable':'uncalibrated'}
  if(Math.hypot(observation.head.x-calibration.baseline.x,observation.head.y-calibration.baseline.y)>.15)return {gaze_x:null,gaze_y:null,gaze_region:'unknown',camera_direction_deviation:null,quality_reason:'head_pose_changed_recalibrate'}
  const {cx,cy}=calibration,x=cx[0]+cx[1]*observation.x+cx[2]*observation.y,y=cy[0]+cy[1]*observation.x+cy[2]*observation.y
  if(!Number.isFinite(x)||!Number.isFinite(y)||Math.abs(x)>5||Math.abs(y)>5)return {gaze_x:null,gaze_y:null,gaze_region:'unknown',camera_direction_deviation:null,quality_reason:'outside_calibrated_range'}
  const deviation=Math.hypot(x-calibration.cameraPoint.x,y-calibration.cameraPoint.y)
  return {gaze_x:x,gaze_y:y,gaze_region:deviation<.15?'camera':x>=0&&x<=1&&y>=0&&y<=1?'screen':'away',camera_direction_deviation:Math.min(10,deviation),quality_reason:null}
}
