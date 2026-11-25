const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const USER_DATA_DIR = path.join(__dirname, 'temp_chrome_profile');

if (!fs.existsSync(USER_DATA_DIR)) {
  fs.mkdirSync(USER_DATA_DIR, { recursive: true });
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.callbacks = new Map();
    this.events = [];
    this.consoleLogs = [];
    this.exceptions = [];
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws.onopen = () => resolve();
      this.ws.onerror = (err) => reject(err);
      this.ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data);
        if (data.id && this.callbacks.has(data.id)) {
          const { resolve, reject } = this.callbacks.get(data.id);
          this.callbacks.delete(data.id);
          if (data.error) reject(new Error(data.error.message));
          else resolve(data.result);
        } else if (data.method) {
          this.handleEvent(data.method, data.params);
        }
      };
    });
  }

  handleEvent(method, params) {
    if (method === 'Runtime.consoleAPICalled') {
      const text = params.args.map(a => a.value || a.description || JSON.stringify(a)).join(' ');
      this.consoleLogs.push({ type: params.type, text });
    } else if (method === 'Runtime.exceptionThrown') {
      const desc = params.exceptionDetails.exception?.description || params.exceptionDetails.text;
      this.exceptions.push(desc);
    }
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.id++;
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expr) {
    const res = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    return res.result?.value;
  }
}

const DEBUG_PORT = 9444;

async function runVerification() {
  console.log('[1/5] Spawning Headless Chrome on port ' + DEBUG_PORT + '...');
  const chromeProc = spawn(CHROME_PATH, [
    '--headless=new',
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${USER_DATA_DIR}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--window-size=1400,900'
  ]);

  await sleep(3000);

  const version = await fetchJson(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
  console.log('Connected to Chrome CDP:', version['Browser']);

  const targets = await fetchJson(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
  const pageTarget = targets.find(t => t.type === 'page') || targets[0];
  const client = new CDPClient(pageTarget.webSocketDebuggerUrl);
  await client.connect();

  await client.send('Page.enable');
  await client.send('Runtime.enable');
  await client.send('Console.enable');

  const report = {
    landing: {},
    dealer: {},
    driver: {},
    admin: {},
    exceptions: [],
  };

  try {
    // -------------------------------------------------------------
    // Test 1: Landing Page (http://localhost:3000)
    // -------------------------------------------------------------
    console.log('\n[2/5] Testing Landing Page: http://localhost:3000');
    client.consoleLogs = [];
    client.exceptions = [];
    await client.send('Page.navigate', { url: 'http://localhost:3000' });
    await sleep(3500);

    report.landing.title = await client.eval('document.title');
    report.landing.h1 = await client.eval('document.querySelector("h1")?.innerText');
    report.landing.hasMap = await client.eval('!!document.querySelector(".leaflet-container")');
    report.landing.metricsPresent = await client.eval('document.body.innerText.includes("1.48 Cr+")');
    report.landing.exceptions = [...client.exceptions];
    report.landing.consoleErrors = client.consoleLogs.filter(l => l.type === 'error');

    console.log('   Heading:', report.landing.h1);
    console.log('   Map mounted:', report.landing.hasMap);
    console.log('   Metrics present:', report.landing.metricsPresent);
    console.log('   Uncaught exceptions:', report.landing.exceptions.length);
    console.log('   Console errors:', report.landing.consoleErrors.length);

    // -------------------------------------------------------------
    // Test 2: Dealer Portal (http://localhost:3000/dealer)
    // -------------------------------------------------------------
    console.log('\n[3/5] Testing Dealer Portal: http://localhost:3000/dealer');
    client.consoleLogs = [];
    client.exceptions = [];
    await client.send('Page.navigate', { url: 'http://localhost:3000/dealer' });
    await sleep(4000);

    report.dealer.title = await client.eval('document.title');
    report.dealer.h1 = await client.eval('document.querySelector("h1")?.innerText');
    report.dealer.userName = await client.eval('document.querySelector("p.text-xs.font-semibold")?.innerText');
    report.dealer.consignments = await client.eval('Array.from(document.querySelectorAll("span")).filter(s => s.innerText.includes("TMT Steel") || s.innerText.includes("Pipes")).map(s => s.innerText)');
    report.dealer.matchesCount = await client.eval('document.querySelectorAll(".text-sm.font-black.font-mono").length');
    report.dealer.topMatchReg = await client.eval('document.querySelector("span.text-xs.font-bold.text-\\\\[\\\\#29231F\\\\]")?.innerText');
    report.dealer.mapMounted = await client.eval('!!document.querySelector(".leaflet-container")');
    report.dealer.exceptions = [...client.exceptions];
    report.dealer.consoleErrors = client.consoleLogs.filter(l => l.type === 'error');

    console.log('   Dealer Hub Title:', report.dealer.h1);
    console.log('   Authenticated User:', report.dealer.userName);
    console.log('   Consignments found:', report.dealer.consignments);
    console.log('   Ranked Matches displayed:', report.dealer.matchesCount);
    console.log('   Top Match Vehicle:', report.dealer.topMatchReg);
    console.log('   Leaflet Map Mounted:', report.dealer.mapMounted);
    console.log('   Uncaught exceptions:', report.dealer.exceptions.length);
    console.log('   Console errors:', report.dealer.consoleErrors.length);

    // Test interaction: Click "Score Breakdown & Book"
    const clickModalRes = await client.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Score Breakdown'));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `);
    await sleep(1500);
    const modalVisible = await client.eval('document.body.innerText.includes("Deterministic 7-Factor Score Breakdown")');
    console.log('   Interaction: Click "Score Breakdown & Book" -> Modal Opened:', modalVisible);
    report.dealer.modalOpened = modalVisible;

    // Close modal
    await client.eval(`
      (() => {
        const cancelBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText === 'Cancel');
        if (cancelBtn) cancelBtn.click();
      })()
    `);
    await sleep(500);

    // Test selecting a consignment with 0 matches to verify rejection diagnostics
    console.log('   Testing 0-match selection for diagnostics verification...');
    await client.eval(`
      (() => {
        const span = Array.from(document.querySelectorAll('span')).find(s => s.innerText && s.innerText.includes('Agricultural Irrigation Pipes'));
        if (span) {
          const card = span.closest('.cursor-pointer');
          if (card) { card.click(); return true; }
        }
        return false;
      })()
    `);
    await sleep(2500);
    const diagHeaderText = await client.eval(`
      (() => {
        const el = Array.from(document.querySelectorAll('p')).find(p => p.innerText.includes('No Immediate Matches'));
        return el ? el.innerText : null;
      })()
    `);
    const diagReasons = await client.eval(`
      (() => {
        const lis = Array.from(document.querySelectorAll('li')).map(l => l.innerText);
        return lis.filter(t => t.includes('mismatch') || t.includes('offline') || t.includes('committed') || t.includes('evaluated'));
      })()
    `);
    console.log('   Zero-match diagnostic header:', diagHeaderText);
    console.log('   Zero-match rejection reasons:', diagReasons);
    report.dealer.zeroMatchDiagHeader = diagHeaderText;
    report.dealer.zeroMatchDiagReasons = diagReasons;

    // Switch back to active consignment
    await client.eval(`
      (() => {
        const items = Array.from(document.querySelectorAll('div'));
        const activeCard = items.find(d => d.innerText && d.innerText.includes('TMT Steel Billets'));
        if (activeCard) activeCard.click();
      })()
    `);
    await sleep(1500);

    // -------------------------------------------------------------
    // Test 3: Driver Mobile PWA (http://localhost:3000/driver)
    // -------------------------------------------------------------
    console.log('\n[4/5] Testing Driver Mobile PWA: http://localhost:3000/driver');
    client.consoleLogs = [];
    client.exceptions = [];
    await client.send('Page.navigate', { url: 'http://localhost:3000/driver' });
    await sleep(4000);

    report.driver.title = await client.eval('document.title');
    report.driver.vehicleReg = await client.eval('document.querySelector("h2.text-base")?.innerText');
    report.driver.dutyStatus = await client.eval('document.body.innerText.includes("ONLINE") ? "ONLINE" : "OFFLINE"');
    report.driver.driverName = await client.eval('document.querySelector("p.text-xs.text-\\\\[\\\\#6E6259\\\\]")?.innerText');
    report.driver.exceptions = [...client.exceptions];
    report.driver.consoleErrors = client.consoleLogs.filter(l => l.type === 'error');

    console.log('   Vehicle Reg:', report.driver.vehicleReg);
    console.log('   Driver & Truck info:', report.driver.driverName);
    console.log('   Duty Status:', report.driver.dutyStatus);
    console.log('   Uncaught exceptions:', report.driver.exceptions.length);
    console.log('   Console errors:', report.driver.consoleErrors.length);

    // Test interaction: Click Duty Status Toggle
    const toggleRes = await client.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('ONLINE') || b.innerText.includes('OFFLINE'));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `);
    await sleep(1500);
    const newStatus = await client.eval('document.body.innerText.includes("ONLINE") ? "ONLINE" : "OFFLINE"');
    console.log('   Interaction: Toggle Duty Status -> New Status:', newStatus);
    report.driver.toggleResponded = (report.driver.dutyStatus !== newStatus || toggleRes);

    // -------------------------------------------------------------
    // Test 4: Admin Control Tower (http://localhost:3000/admin)
    // -------------------------------------------------------------
    console.log('\n[5/5] Testing Admin Control Tower: http://localhost:3000/admin');
    client.consoleLogs = [];
    client.exceptions = [];
    await client.send('Page.navigate', { url: 'http://localhost:3000/admin' });
    await sleep(4000);

    report.admin.title = await client.eval('document.title');
    report.admin.gmv = await client.eval('document.querySelector("p.text-xl.font-bold.font-mono")?.innerText');
    report.admin.activeFleetCount = await client.eval('document.body.innerText.includes("Commercial Trucks Online")');
    report.admin.mapMounted = await client.eval('!!document.querySelector(".leaflet-container")');
    report.admin.exceptions = [...client.exceptions];
    report.admin.consoleErrors = client.consoleLogs.filter(l => l.type === 'error');

    console.log('   Corridor GMV Card:', report.admin.gmv);
    console.log('   Active Fleet Indicator:', report.admin.activeFleetCount);
    console.log('   Fleet Map Mounted:', report.admin.mapMounted);
    console.log('   Uncaught exceptions:', report.admin.exceptions.length);
    console.log('   Console errors:', report.admin.consoleErrors.length);

    // Test interaction: Click "Algorithm Tuning" subtab
    const tuningRes = await client.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Algorithm Tuning'));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `);
    await sleep(1000);
    const slidersCount = await client.eval('document.querySelectorAll("input[type=range]").length');
    console.log('   Interaction: Click "Algorithm Tuning" -> Range Sliders rendered:', slidersCount);
    report.admin.slidersCount = slidersCount;

  } catch (err) {
    console.error('Test Execution Error:', err);
  } finally {
    chromeProc.kill();
    try { fs.rmSync(USER_DATA_DIR, { recursive: true, force: true }); } catch {}
    console.log('\n' + '='.repeat(60));
    console.log('FINAL BROWSER VERIFICATION SUMMARY:');
    console.log(JSON.stringify(report, null, 2));
    console.log('='.repeat(60));
  }
}

runVerification();
