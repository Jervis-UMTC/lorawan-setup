'use strict';
// Offline-only Node.js tests. Executes the exact reviewed Node-RED function in a
// vm sandbox with mocked context; never imports Node-RED or connects to a broker.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, 'i1_node_red_gate.function.js'), 'utf8');
const EUI = 'ac1f09fffe296d29';
function sensor({eui=EUI,temp=24.5,seq=1,fcnt=101,id='uplink-i1-01',time='2026-09-21T01:00:00Z'}={}) {
    return {payload:{deviceInfo:{devEui:eui},object:{temperature_c:temp,test_sequence:seq},
        fCnt:fcnt,deduplicationId:id,time},topic:'application/test'};
}
function execute(message=sensor(), {armed=false,hasCrypto=true,failFlag=false}={}) {
    const flow = {state:armed, reads:0, writes:0,
        get(k) {assert.equal(k,'integrity_alter_next'); this.reads++; if(failFlag) throw Error('flow down'); return this.state;},
        set(k,v) {assert.equal(k,'integrity_alter_next'); this.writes++; if(failFlag) throw Error('flow down'); this.state=v;}};
    const errors = [];
    const wrapper = '(function(msg,flow,global,node){'+source+'\n})';
    const fn = vm.runInNewContext(wrapper, {}, {timeout:200});
    const out=fn(message,flow,{get:(k)=> {assert.equal(k,'crypto'); return hasCrypto?crypto:null;}},
        {error:(s)=>errors.push(s)});
    return {out,flow,errors};
}
test('unchanged EMU passes normal output and exact hash',()=>{
    const {out,flow}=execute(); assert.equal(out[1],null);
    const v=out[0].integrityTest;
    assert.equal(v.status,'ALLOW'); assert.equal(v.initial_hash,v.final_hash);
    assert.match(v.initial_hash,/^[0-9a-f]{64}$/); assert.equal(v.altered,false);
    assert.equal(v.test_sequence,1); assert.equal(flow.writes,0);
});
test('armed EMU changes only temperature and goes quarantine',()=>{
    const input=sensor(); const {out,flow}=execute(input,{armed:true});
    assert.equal(out[0],null);assert.equal(flow.state,false);assert.equal(flow.writes,1);
    const v=out[1].integrityTest;
    assert.equal(v.status,'QUARANTINE');assert.notEqual(v.initial_hash,v.final_hash);
    assert.equal(v.altered,true); assert.equal(out[1].payload.object.temperature_c,34.5);
    assert.equal(input.payload.object.temperature_c,24.5,'original source stays unchanged');
    const pre=JSON.parse(v.initial_record_json),post=JSON.parse(v.final_record_json);
    assert.equal(pre.sensor_value,24.5);assert.equal(post.sensor_value,34.5);
    for(const k of Object.keys(pre)) if(k!=='sensor_value') assert.equal(pre[k],post[k]);
});
test('flag consumed once even when two readings arrive',()=>{
    const first=execute(sensor(),{armed:true});
    const second=execute(sensor({id:'uplink-2',seq:2}),{armed:first.flow.state});
    assert.equal(first.out[1].integrityTest.status,'QUARANTINE');
    assert.equal(second.out[0].integrityTest.status,'ALLOW');
});
test('non-target never touches arm flag or payload',()=>{
    const msg=sensor({eui:'0011223344556677'}),{out,flow}=execute(msg,{armed:true});
    assert.equal(out[0],msg);assert.equal(out[1],null);
    assert.equal(flow.state,true);assert.equal(flow.reads,0);assert.equal(flow.writes,0);
});
test('wrong type/missing sensor value fails closed',()=>{
    for(const temp of [undefined,'24.5',NaN,Infinity]) {
        const msg=sensor({temp}); if(temp === undefined) delete msg.payload.object.temperature_c;
        const r=execute(msg,{armed:true});
        assert.equal(r.out[0],null);assert.equal(r.out[1].integrityTest.status,'INVALID');
        assert.equal(r.flow.state,false);
    }
});
test('missing or malformed test identity fails closed',()=>{
    for(const id of ['',null,5]) {
        const r=execute(sensor({id}),{armed:true});
        assert.equal(r.out[0],null);assert.equal(r.out[1].integrityTest.status,'INVALID');
    }
});
test('missing sensor source sequence fails closed',()=>{
    const msg=sensor();delete msg.payload.object.test_sequence;
    assert.equal(execute(msg).out[1].integrityTest.reason,'invalid_test_record');
});
test('missing/negative frame counter fails closed',()=>{
    for(const fcnt of [null,-1,1.5,undefined]){
        const msg=sensor({fcnt}); if(fcnt === undefined) delete msg.payload.fCnt;
        const r=execute(msg);
        assert.equal(r.out[0],null);assert.equal(r.out[1].integrityTest.status,'INVALID');
    }
});
test('invalid event timestamp fails closed',()=>{
    const r=execute(sensor({time:'not-a-timestamp'}));
    assert.equal(r.out[0],null);assert.equal(r.out[1].integrityTest.reason,'invalid_test_record');
});
test('crypto unavailable quarantines target and disarms',()=>{
    const r=execute(sensor(),{armed:true,hasCrypto:false});
    assert.equal(r.out[0],null);assert.equal(r.out[1].integrityTest.reason,'crypto_unavailable');
    assert.equal(r.flow.state,false);
});
test('flow context inaccessible quarantines target',()=>{
    const r=execute(sensor(),{armed:true,failFlag:true});
    assert.equal(r.out[0],null);assert.equal(r.out[1].integrityTest.reason,'arm_state_unavailable');
});
test('compatible nested sequence field passes',()=>{
    const msg=sensor();delete msg.payload.object.test_sequence;
    msg.payload.object.sequence=31;
    assert.equal(execute(msg).out[0].integrityTest.test_sequence,31);
});
test('test hash is domain-separated by label from production Fabric digest',()=>{
    assert.equal(execute().out[0].integrityTest.hash_scope,'I1_EXPERIMENTAL_JSON_STRINGIFY_NOT_FABRIC');
});
