const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function page(api) {
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, {style: {}, scrollIntoView() {}});
        return elements.get(id);
    };
    const alerts = [];
    const context = vm.createContext({api, console: {log() {}, error() {}},
        protectPage() {}, alert: message => alerts.push(message),
        setTimeout: callback => callback(),
        document: {addEventListener() {}, getElementById: element}});
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/reconciliation.js'), 'utf8'), context);
    vm.runInContext('selectedJobId = "job-1"', context);
    return {context, element, alerts};
}

test('queued jobs display persisted counts only after completion', async () => {
    let polls = 0;
    const ui = page(async (endpoint, method) => {
        if (method === 'POST') return {result_state: 'QUEUED'};
        if (endpoint === '/jobs/job-1') {
            assert.equal(ui.element('resultPanel').style.display, 'none');
            assert.equal(ui.element('jobSelect').disabled, true);
            return {status: ++polls === 1 ? 'PROCESSING' : 'COMPLETED'};
        }
        assert.equal(endpoint, '/reconciliation/job-1/results?page_size=1');
        return {total: 7, matched: 2, mismatched: 3, missing: 2};
    });
    await ui.context.runReconciliation();
    assert.equal(polls, 2);
    assert.equal(ui.element('totalCount').innerText, 7);
    assert.equal(ui.element('mismatchCount').innerText, 3);
    assert.equal(ui.element('jobSelect').disabled, false);
    assert.deepEqual(ui.alerts, []);
});

test('failed background jobs do not display successful results', async () => {
    const ui = page(async (endpoint, method) => method === 'POST'
        ? {result_state: 'QUEUED'} : {status: 'FAILED'});
    await ui.context.runReconciliation();
    assert.equal(ui.element('resultPanel').style.display, 'none');
    assert.match(ui.alerts[0], /Reconciliation failed/);
    assert.equal(ui.element('runBtn').disabled, false);
});

test('polling stops with a pending message if a job does not finish', async () => {
    const ui = page(async (endpoint, method) => method === 'POST'
        ? {result_state: 'QUEUED'} : {status: 'PROCESSING'});
    await ui.context.runReconciliation();
    assert.equal(ui.element('resultPanel').style.display, 'none');
    assert.match(ui.alerts[0], /still running/);
});
