import { useEffect, useRef, useState } from "react";
import { Activity, FileCode2, History, Play, Search, ShieldCheck } from "lucide-react";
import { request } from "../services/api";
import { useTelemetry } from "../hooks/useTelemetry";
import { useAuth } from "../hooks/useAuth";

type Field = {key:string; name?:string; label?:string; kind:string; bytes?:number|null; default?:string; constant?:string; choices?:Record<string,string>};
type Entry = {id:string; name:string; action?:string; group?:string; source:string; risk:string; request_prefix?:string; request_fields?:Field[]; inputs?:Field[]; operation?:string; app?:boolean; ecu?:string; image?:string; notes:string[]};
type Catalog = {error:string|null; metadata:{services:number;scripts:number;cdd_sha256:string;reference_root:string;targets:{ecu:string;instance:number;tx_id:number;rx_id:number}[]}; services:Entry[]; presets:Entry[]};
type Preview = {token:string; name:string; risk:string; request_hex:string|null; confirmation:string; instance:number; tx_id:number; rx_id:number; session:number; security:number; notes:string[]; image?:{name:string;bytes:number;sha256:string;segments:{address:number;length:number}[]}};
type Exchange = {created_at:string; request_hex:string;response_hex?:string;elapsed_ms:number;status:string;error?:string;operation:string};
type Job = {id:string; status:string; summary:{name:string}; result:{message:string; response_hex?:string;listen_only_restored?:boolean;restore_note?:string;warnings?:string[];decoded?:{name:string;value:unknown;label?:string;unit?:string}[]};exchanges:Exchange[]; offset:number};
type Recent = {id:string;name:string;status:string;created_at:string};
const hex = (n:number) => "0x"+n.toString(16).toUpperCase();
const running = (job:Job|null) => !!job && ["queued","running"].includes(job.status);

export function BmsPage() {
  const {deviceId}=useTelemetry();
  const {user}=useAuth();
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [kind,setKind]=useState<"preset"|"cdd">("preset");
  const [query,setQuery]=useState("");
  const [selected,setSelected]=useState("");
  const [values,setValues]=useState<Record<string,string>>({});
  const [instance,setInstance]=useState(1);
  const [ecu,setEcu]=useState("abs_hv");
  const [session,setSession]=useState(0);
  const [security,setSecurity]=useState(0);
  const [imageName,setImageName]=useState("");
  const [imageId,setImageId]=useState(0);
  const [injectCrc,setInjectCrc]=useState(false);
  const [preview,setPreview]=useState<Preview|null>(null);
  const [confirmation,setConfirmation]=useState("");
  const [job,setJob]=useState<Job|null>(null);
  const [recent,setRecent]=useState<Recent[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [mode,setMode]=useState("Waiting for device status");
  const [ready,setReady]=useState(false);
  const [offset,setOffset]=useState(0);
  const previewGeneration=useRef(0);
  const responsePanel=useRef<HTMLElement>(null);
  useEffect(()=>{if(job?.id)responsePanel.current?.scrollIntoView?.({behavior:"smooth",block:"start"});},[job?.id]);
  const entries=catalog ? kind==="cdd" ? catalog.services : catalog.presets : [];
  const entry=entries.find(item=>item.id===selected);
  const fields=entry ? (kind==="cdd" ? entry.request_fields||[] : entry.inputs||[]).filter(f=>!f.constant) : [];
  const targets=catalog?.metadata.targets??[{ecu:"abs_hv",instance:1,tx_id:0x7E4,rx_id:0x7EC}];
  function changeTarget(value:string){const [profile,id]=value.split(":");setEcu(profile);setInstance(Number(id));clearPreview();}
  const canSend=user?.role==="admin" && !user.must_change_password;
  const active=running(job);
  function clearPreview() {previewGeneration.current++;setPreview(null);setConfirmation("");}
  useEffect(()=>{
    const controller=new AbortController();
    request<Catalog>("/api/v1/bms/catalog",{signal:controller.signal}).then(setCatalog).catch(e=>{if(!controller.signal.aborted)setError(e.message);});
    return ()=>controller.abort();
  },[]);
  useEffect(()=>{
    const controller=new AbortController();
    previewGeneration.current++;setJob(null);setPreview(null);setRecent([]);setReady(false);setOffset(0);
    async function refresh() {
      try {
        const [history,stats]=await Promise.all([
          request<{jobs:Recent[]}>("/api/v1/bms/jobs?device_id="+encodeURIComponent(deviceId),{signal:controller.signal}),
          request<{available:boolean;age_seconds?:number;device?:{mode?:string;diag_supported?:boolean;diag_version?:number}}>("/api/v1/can/statistics?device_id="+encodeURIComponent(deviceId),{signal:controller.signal})
        ]);
        if(controller.signal.aborted)return;
        setRecent(history.jobs);
        setReady(!!stats.device?.diag_supported && (stats.device.diag_version??0)>=3 && (stats.age_seconds??999)<5);
        setMode(!stats.available || (stats.age_seconds??999)>=5 ? "Device offline or status is stale" : !stats.device?.diag_supported || (stats.device.diag_version??0)<3 ? "Firmware update required for client workflows" : stats.device.mode==="diagnostic" ? "Diagnostics active · transmit enabled" : stats.device.mode==="listen_only" ? "Listening only · transmit disabled" : "CAN controller unavailable");
      } catch(e) {if(!controller.signal.aborted){setReady(false);setError((e as Error).message);}}
    }
    void refresh();const timer=setInterval(refresh,2500);
    return ()=>{controller.abort();clearInterval(timer);};
  },[deviceId]);
  useEffect(()=>{
    if(!job?.id)return;
    const controller=new AbortController();
    const id=job.id;
    async function refresh(){
      try {const next=await request<Job>("/api/v1/bms/jobs/"+id+"?offset="+offset,{signal:controller.signal});if(!controller.signal.aborted)setJob(next);}
      catch(e){if(!controller.signal.aborted)setError((e as Error).message);}
    }
    void refresh();const timer=active ? setInterval(refresh,750) : undefined;
    return ()=>{controller.abort();if(timer)clearInterval(timer);};
  },[job?.id,active,offset]);
  function choose(id:string) {
    const next=entries.find(item=>item.id===id);if(next?.ecu){setEcu(next.ecu);setInstance(1);}
    setSelected(id);setValues({});clearPreview();setError("");setImageName("");setImageId(0);setInjectCrc(false);
  }
  async function makePreview(runRead=false) {
    setBusy(true);setError("");clearPreview();
    const generation=previewGeneration.current;
    try {
      const next=await request<Preview>("/api/v1/bms/preview",{method:"POST",body:JSON.stringify({device_id:deviceId,kind,entry_id:selected,instance,ecu,session,security,values,image_filename:imageName,image_id:imageId,inject_crc:injectCrc})});
      if(generation!==previewGeneration.current)return;
      if(runRead){
        if(next.risk!=="read"||next.confirmation)throw new Error("This workflow requires review before sending.");
        const result=await request<Job>("/api/v1/bms/jobs",{method:"POST",body:JSON.stringify({token:next.token})});
        if(generation===previewGeneration.current){setJob(result);setOffset(0);}
      }else setPreview(next);
    }
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function quickRead(command:string) {
    if(busy||active||!ready||!canSend)return;
    setBusy(true);setError("");clearPreview();setOffset(0);
    const generation=previewGeneration.current;
    try {const result=await request<Job>("/api/v1/bms/read",{method:"POST",body:JSON.stringify({device_id:deviceId,instance,ecu,command})});if(generation===previewGeneration.current)setJob(result);}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function send() {
    if(!preview)return;
    setBusy(true);setError("");
    try {setJob(await request<Job>("/api/v1/bms/jobs",{method:"POST",body:JSON.stringify({token:preview.token,confirmation})}));setOffset(0);clearPreview();}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function openJob(id:string) {
    try {setJob(await request<Job>("/api/v1/bms/jobs/"+id));setOffset(0);}
    catch(e){setError((e as Error).message);}
  }
  async function cancel(){
    if(!job)return;
    try {await request("/api/v1/bms/jobs/"+job.id+"/cancel",{method:"POST"});}
    catch(e){setError((e as Error).message);}
  }
  return <div className="bms-page">
    <div className="page-heading"><div><div className="eyebrow">BMS WORKSPACE</div><h1>BMS diagnostics</h1><p>BE project commands, clear responses, and a saved record of every request.</p></div><ShieldCheck size={30}/></div>
    <div className={"bms-connection "+(ready?"ready":"")}><Activity size={18}/><strong>{mode}</strong><span>ESP32 + TJA1042 · 500 kbit/s · TX25 / RX26</span></div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {catalog?.error && <div className="error-banner" role="alert">{catalog.error}</div>}
    <div className="bms-summary"><span><b>{catalog?.metadata.services??"—"}</b> CDD services</span><span><b>{catalog?.metadata.scripts??"—"}</b> script workflows</span><span><b>Read-only</b> reference project</span><span><b>Saved</b> request history</span></div>
    <section className="panel bms-quick"><h2>Quick reads</h2><p>Choose the BMS and click a button. Preparation runs automatically and the response appears below. These reads do not reset the BMS.</p>
      <label>Quick-read BMS<select disabled={busy||active} value={ecu+":"+instance} onChange={e=>changeTarget(e.target.value)}>{targets.map(t=><option key={t.ecu+":"+t.instance} value={t.ecu+":"+t.instance}>{t.ecu==="abs_hv_old"?"Legacy bootloader":"BMS"} · {hex(t.tx_id)} → {hex(t.rx_id)}</option>)}</select></label>
      <div className="bms-quick-actions">{[["qr","Read QR code"],["serial","Read serial number"],["hardware","Read hardware part number"],["manufacturing","Read manufacturing serial"],["mode","Read BMS mode"]].map(([command,label])=><button key={command} className="primary-button" disabled={!ready||!canSend||busy||active||!!catalog?.error} onClick={()=>quickRead(command)}><Play size={16}/>{label}</button>)}</div>
      {!ready&&<p>Connect the ESP32 with the latest firmware to enable these reads.</p>}
    </section>
    <div className="bms-workspace">
      <section className="panel bms-library" aria-label="Command library">
        <h2><FileCode2 size={19}/> Command library</h2>
        <div className="bms-tabs"><button className={kind==="preset"?"selected":""} onClick={()=>{setKind("preset");choose("");}}>Script workflows</button><button className={kind==="cdd"?"selected":""} onClick={()=>{setKind("cdd");choose("");}}>CDD services</button></div>
        <label className="bms-search"><Search size={16}/><input aria-label="Search commands" placeholder="Search name, group or request…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
        <div className="bms-command-list">{entries.filter(item=>(item.name+" "+item.action+" "+item.group+" "+item.request_prefix).toLowerCase().includes(query.toLowerCase())).map(item=><button key={item.id} className={selected===item.id?"selected":""} onClick={()=>choose(item.id)}><strong>{item.name}</strong><small>{item.action||item.operation} · <span className={"bms-risk "+item.risk}>{item.risk==="read"?"Read request":item.risk==="critical"?"Critical action":"Changes state"}</span></small></button>)}</div>
      </section>
      <section className="panel bms-request">
        <h2>{entry?.name||"Choose a command"}</h2>
        {!entry ? <p>Select a script workflow for guided steps, or a CDD service to send its exact definition.</p> : <>
          <p className="muted">{entry.source}{entry.action ? " · "+entry.action : ""}</p>
          <div className="bms-fields">
            <label>Target BMS<select disabled={kind==="preset"||busy||active} value={(kind==="preset"?entry.ecu??ecu:ecu)+":"+instance} onChange={e=>changeTarget(e.target.value)}>{targets.map(t=><option key={t.ecu+":"+t.instance} value={t.ecu+":"+t.instance}>{t.ecu==="abs_hv_old"?"Legacy bootloader":"BMS"} · {hex(t.tx_id)} → {hex(t.rx_id)}</option>)}</select></label>
            {kind==="cdd" && <><label>Session before request<select value={session} onChange={e=>{setSession(Number(e.target.value));clearPreview();}}><option value={0}>Keep current session</option><option value={1}>Default (01)</option><option value={2}>Programming (02)</option><option value={3}>Extended (03)</option></select></label><label>Automatic security access<select value={security} onChange={e=>{setSecurity(Number(e.target.value));clearPreview();}}><option value={0}>None</option><option value={1}>Level 01</option><option value={3}>Level 03</option><option value={5}>Level 05</option></select></label></>}
            {fields.map(field=><label key={field.key}>{field.label||field.name}{field.kind==="hex" ? " · "+(field.bytes??"variable")+" bytes (hex)" : ""}{field.choices ? <select value={values[field.key]??field.default??""} onChange={e=>{setValues({...values,[field.key]:e.target.value});clearPreview();}}><option value="">Choose…</option>{Object.entries(field.choices).map(([value,label])=><option key={value} value={value}>{value} · {label}</option>)}</select> : <input type={(entry.request_prefix?.startsWith("2EF16A")||entry.request_prefix?.startsWith("27"))?"password":"text"} autoComplete="off" value={values[field.key]??field.default??""} onChange={e=>{setValues({...values,[field.key]:e.target.value});clearPreview();}}/>}</label>)}
            {entry.image && <label>Replacement image filename (optional)<input placeholder="Use image from reference script" value={imageName} onChange={e=>{setImageName(e.target.value);clearPreview();}}/><small>Local folder: bms_images · Intel HEX only</small></label>}
            {entry.image && <><label>Image slot<select value={imageId} onChange={e=>{setImageId(Number(e.target.value));clearPreview();}}>{Array.from({length:16},(_,i)=><option key={i} value={i}>{i===0?"Default (script behavior)":i}</option>)}</select></label><label className="bms-checkbox"><input type="checkbox" checked={injectCrc} onChange={e=>{setInjectCrc(e.target.checked);clearPreview();}}/> Recalculate image CRC before download</label></>}
          </div>
          {!canSend && <p>Administrator access and a changed initial password are required to send requests.</p>}
          {kind==="preset"&&entry.operation==="read"&&entry.app&&<button className="primary-button" disabled={!canSend||!ready||busy||active} onClick={()=>makePreview(true)}><Play size={16}/> Read now</button>}
          <button disabled={!canSend||busy||active} onClick={()=>makePreview()}>Preview request</button>
          {preview && <div className="bms-preview"><h3>Review before sending</h3>
            <p>Instance {preview.instance} · {hex(preview.tx_id)} → {hex(preview.rx_id)} · Session {preview.session||"unchanged"} · Security {preview.security||"none"}</p>
            {preview.request_hex && <pre>{preview.request_hex}</pre>}
            {preview.image && <><p>{preview.image.name} · {preview.image.bytes.toLocaleString()} bytes · {preview.image.segments.length} segments</p><small>SHA-256</small><pre>{preview.image.sha256}</pre></>}
            {preview.notes.map((note,i)=><p key={i} className="bms-note">{note}</p>)}
            {preview.confirmation && <label className="bms-confirm">This action changes BMS state. Erasing, programming or balancing can interrupt operation. Type CONFIRM to send.<input aria-label="Confirmation" autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label>}
            <button className="primary-button" disabled={!ready||busy||active||!!preview.confirmation&&confirmation!=="CONFIRM"} onClick={send}><Play size={16}/> Send to BMS</button>
            {!ready && <p>Connect the updated ESP32 to enable sending.</p>}
          </div>}
        </>}
      </section>
    </div>
    <section ref={responsePanel} className="panel bms-response"><div className="bms-row"><h2>Response & execution trace</h2>{active && canSend && <button onClick={cancel}>Cancel after current exchange</button>}</div>
      {!job ? <p>Responses appear here after you send a request. Selecting or previewing a command does not transmit.</p> : <>
        <div className="bms-row"><h3>{job.summary.name}</h3><span className={"bms-job-status "+job.status}>{job.status}</span></div>
        <p role="status">{job.result.message}</p>
        {job.result.listen_only_restored!==undefined && <p>{job.result.listen_only_restored?"ESP32 listen-only mode restored.":job.result.restore_note}</p>}
        {job.result.warnings?.map((message,i)=><p key={i} className="bms-note">{message}</p>)}
        {job.result.decoded && job.result.decoded.length>0 && <div className="bms-decoded"><table><thead><tr><th>Signal / field</th><th>Value</th><th>Meaning</th></tr></thead><tbody>{job.result.decoded.map((row,i)=><tr key={i}><td>{row.name}</td><td>{String(row.value)} {row.unit}</td><td>{row.label||"—"}</td></tr>)}</tbody></table></div>}
        <details open><summary>Raw requests and responses · {job.id}</summary><div className="bms-trace">{job.exchanges.map((row,i)=><div key={i}><small>{new Date(row.created_at).toLocaleTimeString()} · {row.elapsed_ms} ms · {row.status} · {row.operation}</small><pre>TX {row.request_hex||"—"}{"\n"}RX {row.response_hex||"—"}</pre>{row.error && <p className="bms-note">{row.error}</p>}</div>)}</div></details>
        <div className="bms-row"><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-200))}>Previous exchanges</button><span>{job.exchanges.length ? "Showing "+(offset+1)+"–"+(offset+job.exchanges.length) : "No exchanges yet"}</span><button disabled={job.exchanges.length<200} onClick={()=>setOffset(offset+200)}>Next exchanges</button></div>
      </>}
    </section>
    <section className="panel bms-history"><h2><History size={19}/> Saved job history</h2><p>Latest 50 jobs for {deviceId}. Sensitive security data is excluded from saved traces.</p><div className="bms-history-list">{recent.map(item=><button key={item.id} disabled={active&&item.id!==job?.id} onClick={()=>openJob(item.id)}><strong>{item.name}</strong><span>{new Date(item.created_at).toLocaleString()}</span><b>{item.status}</b></button>)}</div></section>
  </div>;
}
