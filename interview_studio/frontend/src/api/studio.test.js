import {beforeEach,describe,it,expect,vi} from 'vitest'
const {api}=vi.hoisted(()=>({api:{put:vi.fn(),post:vi.fn()}}))
vi.mock('./client',()=>({api}))
import {studio,mediaMs} from './studio'
beforeEach(()=>vi.clearAllMocks())
describe('studio media wire contract',()=>{
 it('posts a retry to the current session without media',()=>{studio.retryAnswer(7);expect(api.post).toHaveBeenCalledWith('/studio/sessions/7/retry-answer',{})})
 it('sends integer media headers from fractional clock values',()=>{const blob=new Blob(['a'],{type:'audio/webm'});studio.chunk(1,'audio',0,blob,{generation:1,startMs:0.4,endMs:1000.87});const headers=api.put.mock.calls[0][2].headers;expect(headers['X-Media-Start-Ms']).toBe(0);expect(headers['X-Media-End-Ms']).toBe(1001);expect(headers['Content-Type']).toBe('audio/webm')})
 it('sends integer feature timestamps',()=>{studio.features(1,{samples:[{t_ms:24.8,face_valid:true}]});expect(api.post.mock.calls[0][1].samples[0].t_ms).toBe(25)})
 it('rejects invalid media boundaries before network calls',()=>{for(const value of [-1,NaN,Infinity])expect(()=>mediaMs(value)).toThrow();expect(()=>studio.chunk(1,'audio',0,new Blob(['a']),{startMs:20,endMs:10})).toThrow();expect(api.put).not.toHaveBeenCalled()})
})
