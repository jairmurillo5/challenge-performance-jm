import http from 'k6/http';
import { check } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://dummyjson.com';
const RATE = Number(__ENV.TPS || 50);
const DURATION = __ENV.DURATION || '1m';
const USERNAME = __ENV.DUMMYJSON_USERNAME || 'emilys';
const PASSWORD = __ENV.DUMMYJSON_PASSWORD || 'emilyspass';
const PRICE = Number(__ENV.PRODUCT_PRICE || 1.23);
const RUN_ID = __ENV.RUN_ID || `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;

if (![50, 100].includes(RATE)) {
  throw new Error(`TPS debe ser 50 o 100. Valor recibido: ${RATE}`);
}
if (!Number.isFinite(PRICE) || PRICE <= 0) {
  throw new Error(`PRODUCT_PRICE debe ser un número positivo. Valor recibido: ${__ENV.PRODUCT_PRICE}`);
}

const productsCreated = new Counter('products_created');
const productCreateFailures = new Counter('product_create_failures');
const productRequests = new Counter('product_requests');
const productRequestFailureRate = new Rate('product_request_failure_rate');
const productRequestLatency = new Trend('product_req_duration', true);
const productChecks = new Rate('product_checks');

export const options = {
  scenarios: {
    products_add: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.max(RATE * 2, 100),
      maxVUs: Math.max(RATE * 5, 250),
      gracefulStop: '10s',
      tags: { endpoint: 'POST /products/add', target_tps: String(RATE) }
    }
  },
  thresholds: {
    product_request_failure_rate: ['rate<0.01'],
    product_req_duration: ['p(95)<2000'],
    product_checks: ['rate>0.99'],
    dropped_iterations: ['count==0']
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)']
};

/** Login se ejecuta una vez antes del escenario; no forma parte del TPS medido. */
export function setup() {
  const loginPayload = JSON.stringify({
    username: USERNAME,
    password: PASSWORD,
    expiresInMins: 60
  });

  const loginResponse = http.post(`${BASE_URL}/auth/login`, loginPayload, {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'POST /auth/login', phase: 'setup' },
    timeout: '15s'
  });

  const loginOk = check(loginResponse, {
    'login returns HTTP 200': (response) => response.status === 200,
    'login returns accessToken': (response) => Boolean(response.json('accessToken'))
  });

  if (!loginOk) {
    throw new Error(`No fue posible generar el JWT. HTTP ${loginResponse.status}: ${loginResponse.body}`);
  }

  const accessToken = loginResponse.json('accessToken');
  return { accessToken };
}

export default function (data) {
  // __VU + __ITER hacen que el título sea distinto para cada request del escenario.
  const title = `monnet-${RATE}tps-${RUN_ID}-vu${__VU}-iter${__ITER}`;
  const payload = JSON.stringify({ title, price: PRICE });

  const response = http.post(`${BASE_URL}/products/add`, payload, {
    headers: {
      Authorization: `Bearer ${data.accessToken}`,
      'Content-Type': 'application/json'
    },
    tags: { endpoint: 'POST /products/add', target_tps: String(RATE) },
    timeout: '30s'
  });

  productRequests.add(1);
  productRequestLatency.add(response.timings.duration);
  const requestChecks = check(response, {
    'product add returns HTTP 200 or 201': (res) => res.status === 200 || res.status === 201,
    'response echoes unique title': (res) => {
      try { return res.json('title') === title; } catch { return false; }
    },
    'response contains product id': (res) => {
      try { return Number.isInteger(res.json('id')); } catch { return false; }
    }
  });

  productChecks.add(requestChecks);
  const failed = response.status !== 200 && response.status !== 201;
  productRequestFailureRate.add(failed);

  if (requestChecks) {
    productsCreated.add(1);
  } else {
    productCreateFailures.add(1);
  }
}

function metricValue(data, metricName, valueName) {
  return data?.metrics?.[metricName]?.values?.[valueName] ?? null;
}

export function handleSummary(data) {
  const summary = {
    target_tps: RATE,
    configured_duration: DURATION,
    generated_at: new Date().toISOString(),
    metrics: {
      product_requests: metricValue(data, 'product_requests', 'count'),
      iterations: metricValue(data, 'iterations', 'count'),
      products_created: metricValue(data, 'products_created', 'count'),
      product_create_failures: metricValue(data, 'product_create_failures', 'count'),
      http_req_duration: data?.metrics?.product_req_duration?.values ?? null,
      http_req_failed_rate: metricValue(data, 'product_request_failure_rate', 'rate'),
      checks_rate: metricValue(data, 'product_checks', 'rate'),
      dropped_iterations: metricValue(data, 'dropped_iterations', 'count'),
      vus_max: metricValue(data, 'vus', 'max')
    }
  };

  const readable = [
    `Monnet Payments | POST /products/add | target=${RATE} TPS`,
    `Duration configured: ${DURATION}`,
    `Product requests: ${summary.metrics.product_requests ?? 'N/D'}`,
    `Created checks passed: ${summary.metrics.products_created ?? 'N/D'}`,
    `HTTP failure rate: ${summary.metrics.http_req_failed_rate ?? 'N/D'}`,
    `p95 latency (ms): ${summary.metrics.http_req_duration?.['p(95)'] ?? 'N/D'}`,
    `Dropped iterations: ${summary.metrics.dropped_iterations ?? 'N/D'}`
  ].join('\n');

  return {
    [`results/summary-${RATE}tps.json`]: JSON.stringify(data, null, 2),
    [`results/executive-${RATE}tps.json`]: JSON.stringify(summary, null, 2),
    [`results/summary-${RATE}tps.txt`]: `${readable}\n`
  };
}
