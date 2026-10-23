import { FaceLandmarker, PoseLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'
import { irisObservation, fitIrisCalibration, calibratedGaze, sampleLandmarks } from '../utils/landmarks'
export const calibrationTargets=[{x:.5,y:.5,label:'화면 가운데'},{x:.15,y:.2,label:'왼쪽 위'},{x:.85,y:.2,label:'오른쪽 위'},{x:.15,y:.8,label:'왼쪽 아래'},{x:.85,y:.8,label:'오른쪽 아래'},{x:.5,y:.05,label:'카메라 렌즈'}]
export async function createLocalVision(){
  const files=await FilesetResolver.forVisionTasks('/mediapipe/wasm')
  const face=await FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/models/face_landmarker.task',delegate:'CPU'},runningMode:'VIDEO',numFaces:1,outputFacialTransformationMatrixes:true})
  let pose
  try{pose=await PoseLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/models/pose_landmarker_lite.task',delegate:'CPU'},runningMode:'VIDEO',numPoses:1})}catch(error){face.close();throw error}
  let calibration=null,previous=null,closed=false,points=[],viewport=null
  const screen=()=>`${window.innerWidth}x${window.innerHeight}`
  const checkViewport=()=>{if(viewport!==screen())calibration=null}
  const observe=video=>{
    const result=face.detectForVideo(video,performance.now()),value=irisObservation(result.faceLandmarks?.[0]),m=result.facialTransformationMatrixes?.[0]?.data
    // Transformation matrix carries actual estimated head rotation, independent of iris position.
    if(value&&m?.length===16)value.head={x:Math.atan2(m[8],m[10]),y:Math.atan2(-m[9],Math.hypot(m[8],m[10]))}
    return {value,face:result.faceLandmarks?.[0]}
  }
  return {
    resetCalibration(){calibration=null;points=[];viewport=screen()},
    async calibratePoint(video,index){
      if(closed||!video||video.readyState<2)throw new Error('웹캠 영상이 준비되지 않았습니다.')
      if(viewport!==screen())throw new Error('화면 크기가 변경되었습니다. 보정을 취소하고 다시 시작하세요.')
      if(index!==points.length)throw new Error('보정 지점을 처음부터 순서대로 확인하세요.')
      const samples=[]
      for(let i=0;i<30;i++){if(closed)throw new Error('보정이 취소되었습니다.');const result=observe(video).value;if(result)samples.push(result);await new Promise(resolve=>setTimeout(resolve,50))}
      if(samples.length<20)throw new Error('눈동자가 충분히 보이지 않습니다. 눈을 뜨고 조명·안경 반사를 확인하세요.')
      if(index===5){calibration=fitIrisCalibration(points,samples);return calibration}
      points.push({target:calibrationTargets[index],samples});return null
    },
    getCalibration(){checkViewport();return {method:'binocular_iris_headpose_affine',unit:'calibrated_screen_distance',calibrated:!!calibration,point_count:calibration?.point_count??0,validation_error:calibration?.validation_error??null}},
    sample(video,t_ms){
      checkViewport()
      if(closed||!video||video.readyState<2)return {t_ms,face_valid:false,pose_valid:false,...calibratedGaze(null,calibration),normalized_wrist_movement:null}
      const f=observe(video),p=pose.detectForVideo(video,performance.now()).landmarks?.[0],gaze=calibratedGaze(f.value,calibration)
      const result={...sampleLandmarks(f.face,p,previous,null,t_ms),...gaze,face_valid:gaze.gaze_x!==null};previous=p;return result
    },
    close(){closed=true;face.close();pose.close()}
  }
}
