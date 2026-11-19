import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { BmsPage } from "../pages/BmsPage";
import { CanStatistics } from "../components/CanStatistics";
const mocks=vi.hoisted(()=>({request:vi.fn(),role:"admin"}));
vi.mock("../services/api",()=>({request:mocks.request}));
vi.mock("../hooks/useTelemetry",()=>({useTelemetry:()=>({deviceId:"ESP32_001"})}));
vi.mock("../hooks/useAuth",()=>({useAuth:()=>({user:{role:mocks.role,must_change_password:false}})}));
const entry={id:"reset",name:"Reset histograms",operation:"write",source:"reset.bat",risk:"critical",inputs:[],notes:[]};
const catalog={error:null,metadata:{services:55,scripts:44,targets:[{ecu:"abs_hv",instance:1,tx_id:2020,rx_id:2028},{ecu:"abs_hv_old",instance:1,tx_id:1600,rx_id:1616}]},services:[],presets:[entry]};
beforeEach(()=>{
  mocks.role="admin";mocks.request.mockReset();
  mocks.request.mockImplementation((path:string)=>{
    if(path.endsWith("/catalog"))return Promise.resolve(catalog);
    if(path.includes("/can/statistics"))return Promise.resolve({available:true,age_seconds:0,device:{diag_supported:true,diag_version:3,mode:"listen_only"}});
    if(path.endsWith("/preview"))return Promise.resolve({token:"preview",name:entry.name,instance:1,tx_id:1601,rx_id:1617,risk:"critical",confirmation:"CONFIRM",request_hex:"2EFD09FF",notes:[]});
    if(path==="/api/v1/bms/jobs")return Promise.resolve({id:"job",summary:{name:entry.name},status:"completed",result:{message:"BMS returned a positive response",listen_only_restored:true},exchanges:[]});
    return Promise.resolve({jobs:[]});
  });
});
it("selection and preview do not transmit; a state change needs typed confirmation",async()=>{
  render(<BmsPage/>);
  fireEvent.click(await screen.findByRole("button",{name:/Reset histograms/}));
  expect(mocks.request.mock.calls.filter(([path])=>path==="/api/v1/bms/jobs")).toHaveLength(0);
  fireEvent.click(screen.getByRole("button",{name:"Preview request"}));
  const send=await screen.findByRole("button",{name:"Send to BMS"});
  expect(send).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Confirmation"),{target:{value:"CONFIRM"}});
  await waitFor(()=>expect(send).toBeEnabled());
  fireEvent.click(send);
  await waitFor(()=>expect(mocks.request.mock.calls.filter(([path])=>path==="/api/v1/bms/jobs")).toHaveLength(1));
});
it("viewer cannot prepare a transmission",async()=>{
  mocks.role="viewer";render(<BmsPage/>);
  fireEvent.click(await screen.findByRole("button",{name:/Reset histograms/}));
  expect(screen.getByRole("button",{name:"Preview request"})).toBeDisabled();
});
it("changing target invalidates a preview",async()=>{
  render(<BmsPage/>);
  fireEvent.click(await screen.findByRole("button",{name:/Reset histograms/}));
  fireEvent.click(screen.getByRole("button",{name:"Preview request"}));
  await screen.findByText("Review before sending");
  fireEvent.change(screen.getByLabelText("Quick-read BMS"),{target:{value:"abs_hv_old:1"}});
  expect(screen.queryByText("Review before sending")).not.toBeInTheDocument();
});
it("statistics clearly show unavailable hardware without inventing values",async()=>{
  mocks.request.mockResolvedValue({available:false,reason:"Waiting for CAN traffic/status"});
  render(<CanStatistics deviceId="ESP32_001"/>);
  expect(await screen.findByText("Waiting for CAN traffic/status")).toBeInTheDocument();
  expect(screen.getByText(/Voltage, termination resistance/)).toBeInTheDocument();
});
it("discards an in-flight preview if the target changes",async()=>{
  let resolvePreview:(value:unknown)=>void=()=>{};
  const implementation=mocks.request.getMockImplementation()!;
  mocks.request.mockImplementation((path:string,...args:unknown[])=>path.endsWith("/preview") ? new Promise(resolve=>{resolvePreview=resolve;}) : implementation(path,...args));
  render(<BmsPage/>);
  fireEvent.click(await screen.findByRole("button",{name:/Reset histograms/}));
  fireEvent.click(screen.getByRole("button",{name:"Preview request"}));
  fireEvent.change(screen.getByLabelText("Quick-read BMS"),{target:{value:"abs_hv_old:1"}});
  resolvePreview({token:"old",name:entry.name,instance:1,tx_id:1601,rx_id:1617,notes:[]});
  await waitFor(()=>expect(screen.getByRole("button",{name:"Preview request"})).toBeEnabled());
  expect(screen.queryByText("Review before sending")).not.toBeInTheDocument();
});
it("one serial-read click displays the decoded response without a preview or confirmation",async()=>{
  const result={id:"quick-job",status:"completed",summary:{name:"Read serial number"},result:{message:"BMS returned a positive response",listen_only_restored:true,decoded:[{name:"Serial number",value:"BOARD-001"}]},exchanges:[]};
  const implementation=mocks.request.getMockImplementation()!;
  mocks.request.mockImplementation((path:string,...args:unknown[])=>path==="/api/v1/bms/read"||path.includes("/jobs/quick-job")?Promise.resolve(result):implementation(path,...args));
  render(<BmsPage/>);
  const button=await screen.findByRole("button",{name:"Read serial number"});
  await waitFor(()=>expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(await screen.findByText("BOARD-001")).toBeInTheDocument();
  const calls=mocks.request.mock.calls.filter(([path])=>path==="/api/v1/bms/read");
  expect(calls).toHaveLength(1);
  expect(JSON.parse(calls[0][1].body)).toEqual({device_id:"ESP32_001",instance:1,ecu:"abs_hv",command:"serial"});
  expect(mocks.request.mock.calls.filter(([path])=>path.endsWith("/preview"))).toHaveLength(0);
  expect(screen.queryByLabelText("Confirmation")).not.toBeInTheDocument();
});
it("older firmware cannot send the BE address workflows",async()=>{
  const implementation=mocks.request.getMockImplementation()!;
  mocks.request.mockImplementation((path:string,...args:unknown[])=>path.includes("/can/statistics")?Promise.resolve({available:true,age_seconds:0,device:{diag_supported:true,diag_version:2}}):implementation(path,...args));
  render(<BmsPage/>);
  expect(await screen.findByText("Firmware update required for client workflows")).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Read serial number"})).toBeDisabled();
});
