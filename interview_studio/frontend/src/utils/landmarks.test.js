import {describe,it,expect} from 'vitest'
import {direction,wristMovement,sampleLandmarks} from './landmarks'
describe('landmark observations',()=>{
 it('does not infer gaze when calibration or landmarks are missing',()=>{expect(direction([])).toBeNull();expect(sampleLandmarks([],[],null,null,0).camera_direction_deviation).toBeNull()})
 it('normalizes nose direction by eye separation',()=>{const face=[];face[1]={x:.5,y:.6};face[33]={x:.3,y:.4};face[263]={x:.7,y:.4};expect(direction(face).x).toBe(0);expect(direction(face).y).toBeCloseTo(.5)})
 it('requires visible wrists and shoulders',()=>{expect(wristMovement([],[])).toBeNull();const pose=Array.from({length:17},()=>({x:0,y:0,visibility:1}));pose[12].x=1;const previous=structuredClone(pose);pose[15].x=.2;pose[16].x=.2;expect(wristMovement(pose,previous)).toBeCloseTo(.2);pose[15].visibility=.1;expect(wristMovement(pose,previous)).toBeNull()})
})

import {irisObservation,fitIrisCalibration,calibratedGaze} from './landmarks'
describe('calibrated iris gaze',()=>{
 const head={x:0,y:0}
 const rows=(x,y)=>Array.from({length:30},(_,i)=>({x:x+(i%2)*.0001,y,head}))
 const targets=[{x:.5,y:.5},{x:.15,y:.2},{x:.85,y:.2},{x:.15,y:.8},{x:.85,y:.8}]
 const points=()=>targets.map(target=>({target,samples:rows(target.x*.3+.3,target.y*.2)}))
 it('fits personal screen mapping using held-out temporal samples',()=>{const calibration=fitIrisCalibration(points(),rows(.45,0));expect(calibration.validation_error).toBeLessThan(.01);const camera=calibratedGaze({x:.45,y:0,head},calibration);expect(camera.gaze_region).toBe('camera');expect(calibratedGaze({x:.345,y:.16,head},calibration).gaze_region).toBe('screen')})
 it('rejects absent iris, insufficient observations and degenerate calibration',()=>{expect(irisObservation([])).toBeNull();expect(()=>fitIrisCalibration([],[])).toThrow();expect(()=>fitIrisCalibration(targets.map(target=>({target,samples:rows(.5,.1)})),rows(.5,.1))).toThrow()})
 it('marks changed head pose or missing eyes unmeasured instead of scoring',()=>{const c=fitIrisCalibration(points(),rows(.45,0));expect(calibratedGaze({x:.45,y:0,head:{x:.4,y:0}},c).gaze_x).toBeNull();expect(calibratedGaze(null,c).quality_reason).toBe('iris_unobservable')})
})
