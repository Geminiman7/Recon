const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function page() {
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) elements.set(id, {innerHTML: '', innerText: '', textContent: '', hidden: false, appendChild() {}});
        return elements.get(id);
    };
    const context = vm.createContext({
        protectPage() {}, console: {error() {}},
        document: {addEventListener() {}, getElementById: element, querySelector: element, createElement: () => ({})},
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/uploads.js'), 'utf8'), context);
    return {context, element};
}

test('successful list uses direct endpoint and counts uploaded files', async () => {
    const {context, element} = page();
    context.api = async endpoint => {
        assert.equal(endpoint, '/uploads/');
        return [{original_filename: 'company.csv', upload_type: 'COMPANY', status: 'UPLOADED', file_size: 10}];
    };
    await context.loadUploads();
    assert.equal(element('totalUploads').innerText, 1);
    assert.equal(element('companyUploads').innerText, 1);
    assert.equal(element('uploadsListMessage').hidden, true);
});

test('HTML response is an error, not an empty upload list', async () => {
    const {context, element} = page();
    context.api = async () => '<html>Frontend fallback</html>';
    await context.loadUploads();
    assert.match(element('uploadsListMessage').textContent, /unexpected file list/);
    assert.match(element('#uploadsTable tbody').innerHTML, /unavailable/);
    assert.equal(element('totalUploads').innerText, '—');
});

test('failed refresh retains prior files and a retry clears the error', async () => {
    const {context, element} = page();
    context.api = async () => [{original_filename: 'company.csv', upload_type: 'COMPANY'}];
    await context.loadUploads();
    context.api = async () => { throw new Error('Request failed (503)'); };
    await context.loadUploads();
    assert.equal(element('totalUploads').innerText, 1);
    assert.match(element('uploadsListMessage').textContent, /last loaded list/);
    context.api = async () => [];
    await context.loadUploads();
    assert.equal(element('uploadsListMessage').hidden, true);
    assert.equal(element('totalUploads').innerText, 0);
    assert.match(element('#uploadsTable tbody').innerHTML, /No files uploaded yet/);
});
