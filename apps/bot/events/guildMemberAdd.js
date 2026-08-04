const { Events } = require('discord.js');

module.exports = {
	name: Events.GuildMemberAdd,
	async execute(member) {
		const welcomeMsg = `hey, welcome to bits&bytes 👋

we're india's teen-led builder community.
we run hackathons, design/dev squads, and real products — fully student led.

→ head to #roles and pick your city + interests
→ drop a note in #introductions
→ if you want to start a bits&bytes fork in your city, check #forks-info

we ship things here. glad you're in.
— the b&b team`;

		try {
			await member.send(welcomeMsg);
			console.log(`[WELCOME] Sent DM to ${member.user.tag}`);
		} catch (error) {
			console.log(`[WELCOME] Could not send DM to ${member.user.tag} (DMs disabled). Skipping.`);
		}
	},
};
