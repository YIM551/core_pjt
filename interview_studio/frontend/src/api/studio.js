import { api } from './client'

export function mediaMs(value){if(!Number.isFinite(value)||value<0)throw new Error('Invalid media timestamp');return Math.round(value)}
function mediaHeaders(blob,meta){const start=mediaMs(meta.startMs??0),end=mediaMs(meta.endMs??0);if(end<start)throw new Error('Invalid media interval');return {'Content-Type':blob.type||'application/octet-stream','X-Capture-Generation':meta.generation||1,'X-Media-Start-Ms':start,'X-Media-End-Ms':end}}


export const studio = {
  archive:(id,revision)=>api.get(`/studio/sessions/${id}/reports/${revision}`),
  audioBlob:id=>api.get(`/studio/captures/${id}/media/audio`,{responseType:'blob'}),
  questionReady:id=>api.post(`/studio/sessions/${id}/question-ready`,{}),
  enrollSpeaker:(id,body)=>api.post(`/studio/sessions/${id}/speaker-enrollment`,body),
  audioUrl:id=>`/api/v2/studio/captures/${id}/media/audio`,
  retryAnswer:id=>api.post(`/studio/sessions/${id}/retry-answer`,{}),

  transcripts:id=>api.get(`/studio/sessions/${id}/transcripts`),

  transcript:(id,body)=>api.post(`/studio/sessions/${id}/transcripts`,body),

  confirmTranscript:(id,turn,revision)=>api.post(`/studio/sessions/${id}/transcripts/${turn}/${revision}/confirm`,{}),

  features:(id,body)=>api.post(`/studio/captures/${id}/features`,{...body,samples:body.samples.map(sample=>({...sample,t_ms:mediaMs(sample.t_ms)}))}),

  revise: (wid,id,body) => api.post(`/studio/workspaces/${wid}/sources/${id}/revisions`,body),

  removeSource: (wid,id) => api.delete(`/studio/workspaces/${wid}/sources/${id}`),

  upload: (wid,body) => api.post(`/studio/workspaces/${wid}/sources/upload`,body),

  capture: (id, body) => api.post(`/studio/sessions/${id}/captures`, body),

  chunk: (id, track, seq, blob, meta = {}) => api.put(`/studio/captures/${id}/chunks/${track}/${seq}`, blob, {headers:mediaHeaders(blob,meta)}),

  seal: (id, body) => api.post(`/studio/captures/${id}/seal`, body),

  workspaces: () => api.get('/studio/workspaces'),

  workspace: (body) => api.post('/studio/workspaces', body),

  sources: (id) => api.get(`/studio/workspaces/${id}/sources`),

  source: (id, body) => api.post(`/studio/workspaces/${id}/sources`, body),

  sessions: () => api.get('/studio/sessions'),

  create: (body) => api.post('/studio/sessions', body),

  session: (id) => api.get(`/studio/sessions/${id}`),

  control: (id, action, body = {}) => api.post(`/studio/sessions/${id}/${action}`, body, {headers:{'Idempotency-Key':crypto.randomUUID()}}),

  answer: (id, body) => api.post(`/studio/sessions/${id}/answers`, body),

  report: (id) => api.get(`/studio/sessions/${id}/report`),

}





