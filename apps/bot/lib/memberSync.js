const logger = require('./logger');

const TIMEOUT_MS = 8000;

/**
 * Push one member's complete role set to Motherboard the moment Discord changes it.
 * Discord is the only source for access; Motherboard just applies what it is told.
 * `roles` is an array of role ids, or null when the member left the server.
 * Never throws: a failed push is retried once, then left to the periodic full sync.
 */
async function pushMemberRoles(discordId, roles, fetchImpl = fetch) {
	const secret = process.env.API_INTERNAL_SECRET;
	if (!secret) {
		logger.warn('[MEMBER_SYNC] API_INTERNAL_SECRET is not set; skipping live role push.');
		return false;
	}
	const base = process.env.MOTHERBOARD_API_URL || 'http://localhost:8000';
	const request = () => fetchImpl(`${base}/api/sync/member`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-Internal-Secret': secret },
		body: JSON.stringify({ discord_id: discordId, roles }),
		signal: AbortSignal.timeout(TIMEOUT_MS),
	});

	for (let attempt = 1; attempt <= 2; attempt++) {
		try {
			const res = await request();
			if (res.ok) return true;
			// A 4xx will not improve on retry.
			if (res.status < 500) {
				logger.warn(`[MEMBER_SYNC] Motherboard rejected role push for ${discordId} (${res.status}).`);
				return false;
			}
		} catch (err) {
			if (attempt === 2) logger.warn(`[MEMBER_SYNC] Role push failed for ${discordId}: ${err.message}`);
		}
	}
	return false;
}

/** Role ids a guild member holds, without the implicit @everyone role. */
function roleIds(member) {
	return [...member.roles.cache.keys()].filter((id) => id !== member.guild.id);
}

module.exports = { pushMemberRoles, roleIds };
