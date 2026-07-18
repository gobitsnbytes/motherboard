const { SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } = require('discord.js');
const config = require('../config');

module.exports = {
	data: new SlashCommandBuilder()
		.setName('fork-request')
		.setDescription('Initialize a request to start a new B&B node.'),
	async execute(interaction) {
		const flags = config.PRIVACY['fork-request'] ? [MessageFlags.Ephemeral] : [];
		
		const embed = new EmbedBuilder()
			.setTitle(`${config.EMOJIS.save} PROTOCOL_INIT // NEW_NODE_REQUEST`)
			.setDescription("Ready to synchronize your city with the Bits&Bytes network? Please verify your entry via the official registry form below.")
			.setColor(config.COLORS.primary)
            .setThumbnail(interaction.guild.iconURL())
			.addFields(
				{ name: '⌬ VERIFICATION', value: 'Complete the Notion identity form.', inline: true },
				{ name: '⌬ SYNC_STATUS', value: 'Manual review required (ETA: 24-48h). 🛰️', inline: true }
			)
			.setFooter({ text: config.BRANDING.footerText })
			.setTimestamp();

		const button = new ButtonBuilder()
			.setLabel('INITIALIZE_FORM ↗️')
			.setURL('https://perfect-dinghy-781.notion.site/33a49ed2fc33800984e7c28ca3d7cd2a?pvs=105')
			.setStyle(ButtonStyle.Link);

		const row = new ActionRowBuilder().addComponents(button);

		await interaction.reply({
			embeds: [embed],
			components: [row],
			flags
		});
	},
};
