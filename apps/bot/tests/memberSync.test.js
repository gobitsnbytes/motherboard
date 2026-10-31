const { describe, expect, test, beforeEach } = require('bun:test');
const { pushMemberRoles, roleIds } = require('../lib/memberSync');

beforeEach(() => {
	process.env.API_INTERNAL_SECRET = 'secret';
	process.env.MOTHERBOARD_API_URL = 'http://api.test';
});

const reply = (status) => ({ ok: status < 400, status });

describe('pushMemberRoles', () => {
	test('posts the full role set with the internal secret', async () => {
		const calls = [];
		const ok = await pushMemberRoles('42', ['a', 'b'], async (url, init) => { calls.push({ url, init }); return reply(200); });
		expect(ok).toBe(true);
		expect(calls[0].url).toBe('http://api.test/api/sync/member');
		expect(calls[0].init.headers['X-Internal-Secret']).toBe('secret');
		expect(JSON.parse(calls[0].init.body)).toEqual({ discord_id: '42', roles: ['a', 'b'] });
	});

	test('sends null when the member left', async () => {
		let body;
		await pushMemberRoles('42', null, async (_u, init) => { body = JSON.parse(init.body); return reply(200); });
		expect(body.roles).toBeNull();
	});

	test('retries once on a 5xx then gives up without throwing', async () => {
		let n = 0;
		expect(await pushMemberRoles('42', [], async () => { n++; return reply(503); })).toBe(false);
		expect(n).toBe(2);
	});

	test('does not retry a 4xx', async () => {
		let n = 0;
		expect(await pushMemberRoles('42', [], async () => { n++; return reply(401); })).toBe(false);
		expect(n).toBe(1);
	});

	test('a network error never throws', async () => {
		expect(await pushMemberRoles('42', [], async () => { throw new Error('down'); })).toBe(false);
	});
});

test('roleIds drops the implicit @everyone role', () => {
	const member = { guild: { id: 'g' }, roles: { cache: new Map([['g', {}], ['r1', {}]]) } };
	expect(roleIds(member)).toEqual(['r1']);
});
