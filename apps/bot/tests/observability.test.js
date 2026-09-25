const { describe, expect, test } = require('bun:test');

const { beforeSend, beforeSendLog, parseSampleRate, scrubText } = require('../lib/observability');

describe('bot Sentry privacy boundary', () => {
	test('allows only static log events and safe command names', () => {
		expect(beforeSendLog({ message: 'private message' })).toBeNull();
		expect(beforeSendLog({ message: 'bot.command.completed', attributes: {
			command: 'help', user: 'private user',
		} }).attributes).toEqual({ command: 'help' });
		expect(beforeSendLog({ message: 'bot.command.failed', attributes: {
			command: 'private user@example.org',
		} }).attributes).toEqual({});
	});
	test('scrubs secrets from text and clamps trace sampling', () => {
		expect(scrubText('Bearer abc.def and user@example.org')).toBe('Bearer [Filtered] and [email]');
		expect(scrubText('postgresql://user:pass@db/app?token=abc')).toBe(
			'postgresql://[Filtered]@db/app?token=[Filtered]',
		);
		expect(parseSampleRate('-1')).toBe(0);
		expect(parseSampleRate('2')).toBe(1);
		expect(parseSampleRate('not-a-number')).toBe(0);
	});

	test('removes request bodies, headers, users, and sensitive context', () => {
		const event = beforeSend({
			user: { id: 'discord-user', email: 'user@example.org' },
			request: {
				url: 'https://cal.test/auth/callback?code=secret',
				query_string: 'code=secret',
				headers: { authorization: 'Bearer secret', cookie: 'session=secret' },
				cookies: { session: 'secret' },
				data: { password: 'secret' },
			},
			extra: { accessToken: 'secret', note: 'mail user@example.org' },
			exception: { values: [{ type: 'Error', value: 'Bearer secret' }] },
		});

		expect(event.user).toBeUndefined();
		expect(event.request).toEqual({ url: 'https://cal.test/auth/callback' });
		expect(event.extra).toEqual({ accessToken: '[Filtered]', note: 'mail [email]' });
		expect(event.exception.values[0].value).toBe('Bearer [Filtered]');
	});
});
