const { afterEach, beforeEach, expect, test } = require('bun:test');
const cron = require('node-cron');
const Sentry = require('@sentry/node');
const meetingsDb = require('../lib/meetingsDb');
const notion = require('../lib/notion');
const logger = require('../lib/logger');
const startWeeklyBrief = require('../jobs/weeklyBrief');

const original = {
	schedule: cron.schedule,
	captureCheckIn: Sentry.captureCheckIn,
	tryClaimJobRun: meetingsDb.tryClaimJobRun,
	getForks: notion.getForks,
	info: logger.info,
	error: logger.error,
};
let scheduled;
const checkIns = [];
const configurations = [];

beforeEach(() => {
	checkIns.length = 0;
	configurations.length = 0;
	cron.schedule = (expression, callback) => {
		expect(expression).toBe('0 9 * * 1');
		scheduled = callback;
	};
	Sentry.captureCheckIn = (checkIn, configuration) => {
		checkIns.push(checkIn);
		configurations.push(configuration);
		return 'check-in-1';
	};
	meetingsDb.tryClaimJobRun = async () => true;
	notion.getForks = async () => [];
	logger.info = () => {};
	logger.error = () => {};
});

afterEach(() => {
	cron.schedule = original.schedule;
	Sentry.captureCheckIn = original.captureCheckIn;
	meetingsDb.tryClaimJobRun = original.tryClaimJobRun;
	notion.getForks = original.getForks;
	logger.info = original.info;
	logger.error = original.error;
});

test('weekly brief reports a failed Sentry Cron check-in when its channel is missing', async () => {
	startWeeklyBrief({ channels: { fetch: async () => null } });
	await scheduled();

	expect(checkIns).toEqual([
		{ monitorSlug: 'bot-weekly-brief', status: 'in_progress' },
		{ monitorSlug: 'bot-weekly-brief', checkInId: 'check-in-1', status: 'error' },
	]);
	expect(configurations[0]).toEqual({ schedule: { type: 'crontab', value: '0 9 * * 1' } });
});

test('weekly brief reports duplicate scheduled runs as completed no-ops', async () => {
	meetingsDb.tryClaimJobRun = async () => false;
	startWeeklyBrief({ channels: { fetch: async () => { throw new Error('should not fetch'); } } });
	await scheduled();

	expect(checkIns.map(({ status }) => status)).toEqual(['in_progress', 'ok']);
});

test('weekly brief reports caught provider failures without sending exception text in check-ins', async () => {
	meetingsDb.tryClaimJobRun = async () => { throw new Error('private provider response'); };
	startWeeklyBrief({ channels: { fetch: async () => null } });
	await scheduled();

	expect(checkIns.map(({ status }) => status)).toEqual(['in_progress', 'error']);
	expect(JSON.stringify(checkIns)).not.toContain('private provider response');
});
