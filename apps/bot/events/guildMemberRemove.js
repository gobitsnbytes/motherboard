const { Events } = require('discord.js');
const { pushMemberRoles } = require('../lib/memberSync');

module.exports = {
	name: Events.GuildMemberRemove,
	async execute(member) {
		await pushMemberRoles(member.id, null);
	},
};
