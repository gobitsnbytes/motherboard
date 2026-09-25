const Sentry = require('@sentry/node');
const { version } = require('../package.json');

const FILTERED = '[Filtered]';
const SENSITIVE_KEY = /auth(?!or)|cookie|token|secret|passw|dsn|api[-_]?key|credential|private[-_]?key|webhook|(?:^|[-_])otp(?:$|[-_])/i;
const SECRET_PATTERNS = [
	[/\bbearer\s+[A-Za-z0-9._~+/=-]+/gi, `Bearer ${FILTERED}`],
	[/([a-z][a-z0-9+.-]*:\/\/)[^/\s:@]+(?::[^/\s@]*)?@/gi, `$1${FILTERED}@`],
	[/([?&][^=&\s]*(?:token|secret|key|sig|code|pass)[^=&\s]*=)[^&\s#]+/gi, `$1${FILTERED}`],
	[/[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b/g, '[email]'],
];

let initialized = false;
let consoleCaptureInstalled = false;
const capturedErrors = new WeakSet();
const LOG_EVENTS = new Set([
	'bot.lifecycle.boot', 'bot.command.started', 'bot.command.completed', 'bot.command.failed',
	'bot.log.info', 'bot.log.warn', 'bot.log.error', 'bot.log.success',
]);
const LOG_ATTRIBUTES = new Set(['command']);

function scrubText(value) {
	return SECRET_PATTERNS.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), value);
}

function scrub(value, depth = 0) {
	if (depth > 8) return FILTERED;
	if (typeof value === 'string') return scrubText(value);
	if (Array.isArray(value)) return value.map(item => scrub(item, depth + 1));
	if (value && typeof value === 'object') {
		return Object.fromEntries(
			Object.entries(value).map(([key, item]) => [key, SENSITIVE_KEY.test(key) ? FILTERED : scrub(item, depth + 1)]),
		);
	}
	return value;
}

function beforeSend(event) {
	if (event.request) {
		delete event.request.cookies;
		delete event.request.data;
		delete event.request.query_string;
		delete event.request.headers;
		if (event.request.url) event.request.url = scrubText(event.request.url.split(/[?#]/, 1)[0]);
	}
	delete event.user;
	if (event.extra) event.extra = scrub(event.extra);
	if (event.contexts) event.contexts = scrub(event.contexts);
	if (event.message) event.message = scrubText(event.message);
	for (const exception of event.exception?.values || []) {
		if (exception.value) exception.value = scrubText(exception.value);
	}
	for (const crumb of event.breadcrumbs || []) {
		if (crumb.message) crumb.message = scrubText(crumb.message);
		if (crumb.data) crumb.data = scrub(crumb.data);
	}
	return event;
}

function beforeSendLog(log) {
	if (!LOG_EVENTS.has(log.message)) return null;
	log.attributes = Object.fromEntries(
		Object.entries(log.attributes || {}).filter(([key, value]) =>
			LOG_ATTRIBUTES.has(key) && typeof value === 'string' && /^[a-z0-9_-]{1,64}$/.test(value),
		),
	);
	return log;
}

function recordOperationalLog(event, attributes = {}) {
	if (!initialized || !LOG_EVENTS.has(event)) return;
	Sentry.logger.info(event, attributes);
}

function parseSampleRate(raw) {
	const parsed = raw ? Number(raw) : Number.NaN;
	return Number.isFinite(parsed) ? Math.min(Math.max(parsed, 0), 1) : 0;
}

function initObservability() {
	if (initialized || !process.env.SENTRY_DSN) return false;
	const sha = process.env.GIT_SHA || process.env.GITHUB_SHA || '';
	Sentry.init({
		dsn: process.env.SENTRY_DSN,
		environment: process.env.SENTRY_ENVIRONMENT || process.env.NODE_ENV || 'development',
		release: process.env.SENTRY_RELEASE || `bnb-bot@${version}${sha ? `+${sha.slice(0, 12)}` : ''}`,
		tracesSampleRate: parseSampleRate(process.env.SENTRY_TRACES_SAMPLE_RATE),
		// Fatal errors are flushed by our handlers below. Removing the default
		// handlers prevents duplicate issues and keeps exit behavior explicit.
		integrations: defaults => defaults.filter(
			integration => !['OnUncaughtException', 'OnUnhandledRejection', 'LocalVariablesAsync'].includes(integration.name),
		),
		beforeSend,
		beforeSendLog,
		dataCollection: {
			userInfo: false,
			cookies: false,
			httpHeaders: { request: false, response: false },
			httpBodies: [],
			urlQueryParams: false,
			graphQL: { document: false, variables: false },
			genAI: { inputs: false, outputs: false },
			databaseQueryData: false,
			queues: false,
			stackFrameVariables: false,
		},
	});
	initialized = true;
	return true;
}

function captureException(error, context = {}) {
	if (!(error instanceof Error) || !process.env.SENTRY_DSN || capturedErrors.has(error)) return undefined;
	capturedErrors.add(error);
	const { tags = {}, ...extra } = context;
	return Sentry.captureException(error, {
		tags: { service: 'discord-bot', ...tags },
		extra: scrub(extra),
	});
}

function installConsoleErrorCapture() {
	if (consoleCaptureInstalled) return;
	consoleCaptureInstalled = true;
	const original = console.error.bind(console);
	console.error = (...args) => {
		const error = args.find(arg => arg instanceof Error);
		if (error) captureException(error, { tags: { source: 'console.error' } });
		original(...args);
	};
}

async function flush(timeout = 2000) {
	if (!process.env.SENTRY_DSN) return true;
	return Sentry.flush(timeout);
}

module.exports = {
	beforeSend,
	beforeSendLog,
	captureException,
	flush,
	initObservability,
	installConsoleErrorCapture,
	parseSampleRate,
	recordOperationalLog,
	scrubText,
};
