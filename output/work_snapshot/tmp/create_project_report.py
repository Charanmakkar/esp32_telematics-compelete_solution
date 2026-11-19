from pathlib import Path
import json
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.utils import ImageReader
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/reports'
D=json.loads((ROOT/'tmp/prompt-metrics.json').read_text())
PDF=OUT/'NavSphere_Project_and_AI_Usage_Report.pdf'
c=canvas.Canvas(str(PDF),pagesize=A4)
c.setTitle('NavSphere Project and AI Usage Report')
c.setAuthor('Prepared with Codex for Charanpreet')
W,H=A4; M=42; y=0; page=0
styles={
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=10,leading=14,textColor=colors.HexColor('#243244'),spaceAfter=8),
 'small':ParagraphStyle('small',fontName='Helvetica',fontSize=8.4,leading=11.5,textColor=colors.HexColor('#445365')),
 'cell':ParagraphStyle('cell',fontName='Helvetica',fontSize=9,leading=12,textColor=colors.HexColor('#243244')),
 'head':ParagraphStyle('head',fontName='Helvetica-Bold',fontSize=9,leading=12,textColor=colors.white),
}
def p(text,style='body'):
 global y
 obj=Paragraph(text,styles[style]);_,h=obj.wrap(W-2*M,1000);obj.drawOn(c,M,y-h);y-=h+8
def h(text):
 global y
 y-=5;c.setFillColor(colors.black);c.setFont('Helvetica-Bold',12);c.drawString(M,y-12,text);y-=25
def table(headers,rows,widths):
 global y
 data=[[Paragraph(escape(str(v)),styles['head']) for v in headers]]
 data += [[Paragraph(escape(str(v)).replace('\n','<br/>'),styles['cell']) for v in row] for row in rows]
 t=Table(data,colWidths=widths,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#172B40')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F1F5F8'),colors.white]),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#172B40'))]))
 _,height=t.wrap(W-2*M,1000);t.drawOn(c,M,y-height);y-=height+13
def new(title,sub='',wide=False):
 global W,H,y,page
 if page: finish()
 W,H=landscape(A3) if wide else A4;c.setPageSize((W,H));page+=1
 c.setFillColor(colors.HexColor('#486176'));c.setFont('Helvetica-Bold',8);c.drawString(M,H-32,'NAVSPHERE  /  PROJECT DELIVERY REPORT')
 y=H-65;c.setFillColor(colors.black);c.setFont('Helvetica-Bold',21);c.drawString(M,y,title);y-=25
 if sub:p(sub,'small')
 y-=9
def finish():
 assert y>=43, f'Page {page} content extends into footer: {y}'
 c.setFillColor(colors.HexColor('#667686'));c.setFont('Helvetica',8)
 c.drawString(M,24,'12 November 2026  |  Prepared for Charanpreet')
 c.drawRightString(W-M,24,f'{page}');c.showPage()

new('NavSphere project and AI usage','ESP32S WROOM telemetry platform  |  Development and verification on 11 and 12 November 2026')
p('NavSphere now delivers real readings from six ESP32 ADC inputs through authenticated MQTT, a Python backend and MariaDB to a live React dashboard. This report records the user inputs, available usage information, implemented features, AI work and verification evidence.')
h('Prompt count and size')
total=D['totals']; master=D['master']['original_attachment']
table(['Measure','Verified result'],[
 ('User inputs in the two audited Codex chats','15 total: 9 development inputs and 6 recovery, hardware, reporting and relaunch inputs'),
 ('Input composition','11 ordinary text messages, 3 clarification replies and 1 image-only message'),
 ('Current chat only','6 user messages, through the relaunch and report-update request'),
 ('Original master development prompt',f"{master['words']:,} words; {master['characters']:,} characters; {master['file_bytes']:,} bytes (31.53 KiB)"),
 ('User message text excluding attachment',f"{total['words']:,} words; {total['characters']:,} characters"),
 ('Combined text including original attachment once',f"{total['words']+master['words']:,} words; {total['characters']+master['characters']:,} characters"),
 ('Exact model tokens','Not measured by this audit; text sizes are not billed-token totals'),
], [210,W-2*M-210])
h('Credits and account usage')
p('<b>Total credits used for this project: unavailable.</b> The account usage tool returned no project billing ledger or consumed-credit total. A missing balance is not evidence of zero cost.')
p('The account snapshot showed <b>4% of the weekly allowance used</b> and no numeric credit balance. This is an account-wide rate-limit measure, not a project credit total, and cannot be converted into credits spent. The snapshot was taken during this relaunch/report revision. The earlier report showed 2%; neither percentage measures project credits.')
p('Scope: the original development chat and this recovery chat only. The separate ChatGPT planning conversation, other chats, system instructions, AI responses and tool output are excluded. The original attachment is counted once, not as a separate user message.','small')

new('Prompt register','One row per user input  |  Normalized text sizes  |  Original attachment listed separately')
labels=['Initial implementation request','Board and GPIO clarification','ESP32S board confirmation','Six channel scope clarification','Build configuration repair','Build still failing','IntelliSense error screenshot','SDK quick button repair','Gear icon clarification','Recover missing project files','Start services and verify ESP32','Create usage and GUI report','Add features and AI work','Remap A and B to GPIO2 and GPIO0','Relaunch project and update AI report']
rows=[]
for i,(row,label) in enumerate(zip(D['messages'],labels),1):
 rows.append((str(i),label,{'text':'Text','clarification':'Reply','image':'Image'}[row['kind']],str(row['words']) if row['kind']!='image' else '-',str(row['characters']) if row['kind']!='image' else '-'))
table(['#','Purpose','Type','Words','Chars'],rows,[27,265,57,48,W-2*M-397])
p('Rows 1 to 9 belong to the original development chat. Rows 10 to 15 belong to the current recovery and hardware chat. An image-only message counts as one input; its pixel data has no text character count.','small')
h('Master prompt versions')
table(['Version','Words','Characters','File bytes'],[
 ('Original pasted attachment','4,338','32,235','32,289'),
 ('Current repository master prompt',f"{D['master']['current_master']['words']:,}",f"{D['master']['current_master']['characters']:,}",f"{D['master']['current_master']['file_bytes']:,}"),
],[240,75,95,W-2*M-410])
p('Method: decode HTML entities, normalize line endings, trim surrounding whitespace, count whitespace-separated words and Unicode characters. Clarification messages contribute answer text only; app wrappers and attachment-path metadata are excluded. File bytes are the on-disk size and can differ because of line endings. The modified repository prompt is shown for comparison and is not added again to the combined total.','small')

new('Firmware and data platform features','Implemented capability inventory  |  Final scope is six onboard ADC1 channels')
table(['Area','Implemented features'],[
 ('ESP32 firmware','Native ESP-IDF 6.0.2 C11 and FreeRTOS; separate configuration, ADC, Wi-Fi, MQTT and command modules; ESP32 target; root and standalone build support.'),
 ('Six analog inputs','GPIO32, 33, 34, 35, 36 and 39; 12-bit ADC; configurable averaging; eFuse-based calibration; millivolt and raw-count reporting; per-channel validity mask.'),
 ('Acquisition and buffering','Nominal 100 ms acquisition and publication; independent tasks; bounded four-sample queue; newest-sample publication; bounded MQTT outbox; stale and dropped-sample accounting.'),
 ('Wi-Fi and device identity','NVS provisioning; Wi-Fi reconnection with bounded backoff; SNTP clock synchronization; device ID, boot ID, sequence and uptime in telemetry.'),
 ('GPIO controls','A on GPIO2 and B on GPIO0; active-high 0/1 commands; safe LOW startup; reset on observed network loss or invalid clock; configurable inactivity watchdog.'),
 ('Command integrity','Strict JSON and field checks; unique command IDs; expiry and future-time checks; retained-message rejection; bounded replay guard; accepted, applied or rejected acknowledgements.'),
 ('MQTT transport','Authenticated Mosquitto; device-scoped ACLs; QoS 1; telemetry, command, acknowledgement and status topics; retained status and last will; reconnect handling.'),
 ('Python backend','FastAPI and Pydantic validation; bounded ingress queue; database retries; authenticated REST; WebSocket received and committed-persistence events; health, readiness and counters.'),
 ('Database and history','Existing MariaDB reused; Alembic migrations; telemetry, users, sessions, devices, commands and audit records; unique device/boot/sequence deduplication; indexed latest/history queries.'),
 ('Bounded queries','Per-channel and combined history; min, max, average and count; SQL time-bucket downsampling; bounded result size and date window; null gaps for invalid readings.'),
],[112,W-2*M-112])
p('The local deployment uses authenticated plaintext MQTT. TLS configuration and production validation are implemented, but production TLS and encrypted device storage were not deployed or validated in this session.','small')

new('Dashboard security and operations','User-facing features and supporting delivery tools')
table(['Area','Implemented features'],[
 ('Dashboard overview','Live device status; receive rate and persistence counters; six-channel cards with GPIO mapping, current values and sparklines; combined live chart; service health and freshness indicators.'),
 ('Channel analytics','Six dedicated routes; live and historical views; predefined and custom time ranges; minimum, maximum and average; brush zoom and pan; plotted-data CSV export with UTC timestamps.'),
 ('User experience','Responsive React and TypeScript interface; dark and light themes; local font assets; explicit loading, error, stale and unavailable states; visibly labelled simulator data.'),
 ('Control interface','Administrator A/B controls; pending, accepted, applied, rejected and timed-out command states; command history; no optimistic claim that an output was applied.'),
 ('Account security','Salted scrypt password hashes; hashed random session tokens; HttpOnly/SameSite cookies; CSRF protection; role checks; login rate limits; session expiry and revocation; account password change.'),
 ('Production checks','Reject default credentials and insecure production cookie, origin, database and MQTT settings; check stored active accounts for the default password; audit administrative actions.'),
 ('Service operations','Windows setup/start/stop scripts; owned-process shutdown; portable dependencies; database migrations; local credential files; optional simulator; configurable backend and broker settings.'),
 ('Maintenance and release','Database backup helper; bounded retention command with dry run; source/document ZIP packaging; firmware manifest and SHA-256 checksums; documentation export; optional Docker Compose files.'),
 ('Developer support','Swagger, ReDoc and OpenAPI; firmware/API/deployment/architecture/testing documentation; VS Code build task, compiler include database and SDK Configuration Editor fixes.'),
],[112,W-2*M-112])
h('Current access and operating boundaries')
p('Dashboard: <link href="http://localhost:5173/" color="#126789">http://localhost:5173/</link>. Device ESP32_001 is connected over Wi-Fi. The browser shows real hardware measurements; the separate simulator is not the active data source.')
p('The administrator password has been changed since the original setup. A fresh browser session requires the current password. Docker execution, production TLS/encryption, electrical output measurements, calibrated sensor accuracy and a long-duration soak remain outside completed validation. Offline telemetry is dropped and counted; there is no flash journal or durable backend disk spool.','small')

new('Work completed by AI','Development, recovery and live hardware commissioning')
table(['Phase','Work performed'],[
 ('Requirements and design','Inspected the empty ESP-IDF skeleton; clarified ESP32S-WROOM and six onboard channels; updated the master prompt; separated firmware, backend, frontend, database, broker, simulator and documentation.'),
 ('Implementation','Built the firmware and FreeRTOS tasks, MQTT protocol, FastAPI services, database schema/migrations, React dashboard, analytics, controls, authentication, scripts, tests and delivery documentation.'),
 ('Build troubleshooting','Added a root ESP-IDF entry point; corrected IntelliSense compiler/include settings; configured quiet SDK reporting to resolve the configuration editor issue; rebuilt root and standalone firmware.'),
 ('Workspace recovery','Compared the original folder with the workspace; restored 15,449 missing files including the frontend and Node executable; preserved existing files; repaired editor/MQTT paths; rebuilt and checked release contents.'),
 ('Local services and credentials','Started the existing MariaDB and local services; fixed provisioning environment-variable names; moved Wi-Fi values out of source; checked credentials against the saved profile; enabled the laptop MQTT listener for the board.'),
 ('ESP32 commissioning','Detected COM3; backed up all 4 MB of flash; generated private NVS settings; flashed firmware/configuration and verified write hashes; confirmed Wi-Fi, MQTT and clock synchronization.'),
 ('Verification and handover','Ran automated and live tests; verified real six-channel readings and database persistence; inspected the GUI; saved screenshots, results and a refreshed release archive; left services and dashboard running.'),
],[112,W-2*M-112])
h('User contributions and scope')
p('The user supplied the master requirements, selected the board and six-channel scope, provided the original file location and Wi-Fi configuration, connected the ESP32, and steered troubleshooting. AI performed the software and local setup work; physical sensor wiring and measurement accuracy were not independently established.')
p('AI activity is summarized from the two audited chats and project artifacts. It is not a claim of measured human-hours saved, line-by-line authorship of third-party dependencies, or certified production readiness.','small')

new('Verification results and evidence','Latest hardware results take precedence over the initial implementation report')
table(['Check','Result'],[
 ('Backend / frontend / simulator tests','28 / 15 / 10 passed; 53 application tests total'),
 ('Additional checks','Backend lint and dependency consistency; firmware host tests; owned-process shutdown test; Python/JSON parsing; local documentation links and archive integrity passed'),
 ('Builds','Frontend production build and both ESP32 firmware configurations passed; firmware size 988,272 bytes; 69% application partition space free'),
 ('Simulated live integration','300/300 samples stored in MariaDB over 30.002 seconds, 9.999 Hz; MQTT A/B acknowledgements, duplicate protection, API validation, WebSocket and all channel histories passed'),
 ('Real hardware interval','299/299 expected sequence readings stored in a roughly 30-second window; all six channels valid; no additional device-reported drops; SNTP time valid'),
 ('Hardware WebSocket observation','298 received and 297 persisted events observed within the bounded socket window. This is evidence of live streaming, not a claim that every event was captured at both window boundaries.'),
 ('Startup loss and controls','77 samples discarded before MQTT startup completed; no increase in the measured window. Both A and B stayed LOW; physical outputs were not toggled.'),
 ('GUI verification','Live overview, device/service health, six ADC cards and Analog 01 analytics visually inspected. Captured GUI screenshots are included in the final three pages.'),
],[148,W-2*M-148])
h('Evidence sources')
p('Local project evidence: IMPLEMENTATION_REPORT.md; firmware/README.md; backend/README.md; frontend/README.md; docs/api/API_REFERENCE.md; docs/testing/integration-results.json; output/testing/recovery-results.json; output/testing/hardware-live-results.json; output/testing/gpio-remap-results.json; output/testing/relaunch-results.json. The initial report predates flashing; the hardware report records the completed 12 November board verification.','small')
p('Prompt evidence: the full available user-message history of “Build NavSphere telemetry platform” and “Recover missing project files”, the original pasted master-prompt attachment, and MASTER DEVELOPMENT PROMPT.md. Usage evidence: current Codex account usage snapshot. Separate ChatGPT planning messages are not included.','small')
p('Credit interpretation reference: <link href="https://learn.chatgpt.com/docs/pricing" color="#126789">OpenAI ChatGPT and Codex pricing documentation</link>. Tokens include more than user prompt text; account allowance percentages do not establish this project\'s billed-credit consumption.','small')

new('Latest changes and AI involvement','Report revision after GPIO remapping and project relaunch')
p('The project services have been relaunched. The existing MariaDB server was retained; MQTT, the FastAPI backend and the frontend were restarted using the project scripts. The ESP32 reconnected automatically and resumed publishing hardware telemetry.')
h('Current hardware mapping')
table(['Control','GPIO','Behavior'],[('A','2','Active high; LOW after firmware startup and on safety reset'),('B','0','Active high; LOW after firmware startup and on safety reset')],[85,65,W-2*M-150])
p('GPIO0 and GPIO2 are boot strapping pins. GPIO0 must be HIGH during reset for normal boot; do not attach a Control B pull-down. GPIO2 must be LOW or floating for serial flashing. Reset-time load behavior needs suitable external circuitry.')
h('AI work in this revision')
p('AI updated both firmware configurations, Kconfig defaults, GUI labels, Markdown documentation and release metadata. Host tests now exercise GPIO calls with stubs and verify that A routes to GPIO2, B routes to GPIO0, and both return LOW on disconnect and watchdog expiry. Both firmware builds and all 15 frontend tests passed. The firmware was flashed on COM3 with write-hash verification, preserving Wi-Fi and MQTT credentials.')
p('For this relaunch, AI restarted the owned application processes, checked database and MQTT readiness, verified fresh six-channel hardware records and reopened the dashboard. A visual check found and corrected the remaining old GPIO labels on the control cards; frontend tests and the production build passed again. No physical output was deliberately toggled. The report now includes the remap and relaunch evidence.')
h('AI used and accounting limits')
p('Codex desktop was the AI coding and automation assistant. It used repository inspection and editing, PowerShell/Python scripts, ESP-IDF build and flashing tools, automated tests, browser inspection, official documentation lookup and PDF authoring. The original development chat also records delegated AI subtasks; this recovery chat used direct execution.')
p('An exact per-turn model/version, inference-token total, subagent-inclusive billing total and project-credit expenditure are not exposed by the audited chat and account tools. They are therefore not asserted. The verified account snapshot is 4% of a weekly usage allowance, not four credits and not a project-specific cost.')
p('Prompt-count cutoff: the latest relaunch/report-update request, before any sign-in coordination replies. Fresh screenshots show the signed-in application after restart. Sign-in coordination and credential messages are excluded from prompt metrics and from this report.','small')

new('Recorded interaction time','Measured from the two audited Codex chat histories  |  Completed sessions only')
p('The total recorded work-session time is <b>1 hour 46 minutes 40 seconds</b> across nine completed sessions. This is the sum of the app-recorded duration of each completed turn, including tool execution, builds, waiting and clarification within those turns.')
table(['Measure','Recorded duration'],[
 ('Original development chat','1 hour 8 minutes 6 seconds'),
 ('Recovery and hardware chat','38 minutes 34 seconds'),
 ('Total completed work-session time','1 hour 46 minutes 40 seconds'),
 ('Elapsed span including gaps','21 hours 9 minutes 9 seconds'),
],[260,W-2*M-260])
h('Session breakdown')
timing=json.loads((OUT/'interaction-time.json').read_text())
names=['Initial platform implementation','Build configuration repair','Root build and IntelliSense repair','SDK Configuration Editor repair','Workspace recovery and builds','Live services and ESP32 commissioning','Project and AI usage report','GPIO2 and GPIO0 remap and flash','Project relaunch and report revision']
rows=[]
for label,turn in zip(names,timing['turns']):
 seconds=round(turn['durationMs']/1000);minutes,secs=divmod(seconds,60)
 rows.append((label,f'{minutes} min {secs:02d} sec'))
table(['Work session','Recorded duration'],rows,[350,W-2*M-350])
h('Scope and interpretation')
from datetime import datetime, timezone, timedelta
ist=timezone(timedelta(hours=5,minutes=30))
start=datetime.fromtimestamp(timing['first'],ist).strftime('%d %B %Y at %H:%M:%S IST')
end=datetime.fromtimestamp(timing['last'],ist).strftime('%d %B %Y at %H:%M:%S IST')
p(f'The elapsed span runs from {start} to {end}. It includes idle time between requests and the overnight gap. Recorded work-session time excludes those between-turn gaps.')
p('This timing measurement and report-update turn is still in progress and is excluded. The separate ChatGPT planning conversation is also excluded. Parallel AI subtasks are not added again to parent-session wall time. Durations are rounded to the nearest second from millisecond records; rounded row totals can differ slightly from the rounded overall total.','small')
p("These records do not measure the user's hands-on time, uninterrupted AI inference time, or billable credits. A completed session can include waiting for tools or user input. Source: completed-turn startedAt, completedAt and durationMs fields from the Codex chat-history tool.",'small')


def panel(path,x,top,width,start,end):
 im=Image.open(path);iw,ih=im.size;scale=width/iw;height=(end-start)*scale
 c.saveState();clip=c.beginPath();clip.rect(x,top-height,width,height);c.clipPath(clip,stroke=0)
 c.drawImage(ImageReader(im),x,top-(ih-start)*scale,width=width,height=ih*scale)
 c.restoreState()
 return height

new('Live telematics dashboard','Captured 12 November 2026 around 10:47 IST  |  Same genuine screenshot shown in two readable sections',wide=True)
top=y;gap=22;pw=430;sx=(W-2*pw-gap)/2
panel(OUT/'telematics-overview.png',sx,top,pw,0,944)
panel(OUT/'telematics-overview.png',sx+pw+gap,top,pw,944,1906)
y=top-962*pw/653-12
p('Left: live status, current-session received and persisted records, all six channels and signal chart. Right: connected services, physical GPIO labels, six channel readings and persistence timestamps. Values are a capture-time snapshot; the rate card is a short-window estimate.','small')

new('Channel analytics screenshot','Captured 12 November 2026 around 10:48 IST  |  Analog 01 on GPIO32  |  Genuine screenshot in two sections',wide=True)
top=y
panel(OUT/'telematics-analytics.png',sx,top,pw,0,568)
panel(OUT/'telematics-analytics.png',sx+pw+gap,top,pw,568,1350)
y=top-782*pw/653-18
p('The analytics view shows current, minimum, maximum and average readings; live/historical controls; range selection; CSV export; time-series plotting and zoom handles. Unconnected ADC pins may fluctuate, so visual signal activity alone does not establish sensor accuracy.','small')
new('Updated device controls','Captured 12 November 2026 around 10:48 IST  |  Visible viewport of the control page')
img=Image.open(OUT/'telematics-controls.png');iw,ih=img.size;ww=W-2*M;hh=ih*ww/iw
c.drawImage(ImageReader(img),M,y-hh,width=ww,height=hh);y-=hh+18
p('Both the notice and the individual control cards show A on GPIO2 and B on GPIO0. Both controls show Confirmed OFF. The screenshot records the current state; no ON or OFF command was sent during this relaunch verification.')
p('The full command history continues below this viewport. This image is a genuine application screenshot and does not expose login credentials.','small')
finish();c.save()
print(PDF)
