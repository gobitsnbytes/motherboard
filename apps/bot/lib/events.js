/**
 * 📅 EVENT MANAGEMENT SYSTEM
 * Manages event lifecycle and tracking
 */

// Event lifecycle stages
const EVENT_STAGES = ['Idea', 'Planned', 'Approved', 'Executing', 'Completed'];

// Event types
const EVENT_TYPES = ['workshop', 'hackathon', 'meetup', 'other'];

/**
 * Get next stage in the event lifecycle
 * @param {string} currentStage - Current stage name
 * @returns {string|null} - Next stage or null if at end
 */
function getNextStage(currentStage) {
	const currentIndex = EVENT_STAGES.indexOf(currentStage);
	if (currentIndex === -1 || currentIndex >= EVENT_STAGES.length - 1) {
		return null;
	}
	return EVENT_STAGES[currentIndex + 1];
}

/**
 * Get previous stage in the event lifecycle
 * @param {string} currentStage - Current stage name
 * @returns {string|null} - Previous stage or null if at start
 */
function getPreviousStage(currentStage) {
	const currentIndex = EVENT_STAGES.indexOf(currentStage);
	if (currentIndex <= 0) {
		return null;
	}
	return EVENT_STAGES[currentIndex - 1];
}

/**
 * Get stage emoji
 * @param {string} stage - Stage name
 * @returns {string} - Emoji for the stage
 */
function getStageEmoji(stage) {
	const emojis = {
		'Idea': '💡',
		'Planned': '📋',
		'Approved': '✅',
		'Executing': '🚀',
		'Completed': '🎉',
	};
	return emojis[stage] || '📅';
}

/**
 * Get event type emoji
 * @param {string} type - Event type
 * @returns {string} - Emoji for the type
 */
function getTypeEmoji(type) {
	const emojis = {
		'workshop': '🛠️',
		'hackathon': '💻',
		'meetup': '👥',
		'other': '📌',
	};
	return emojis[type?.toLowerCase()] || '📅';
}

/**
 * Format event for display
 * @param {Object} event - Event object
 * @returns {string} - Formatted string
 */
function formatEventDisplay(event) {
	const typeEmoji = getTypeEmoji(event.type);
	const stageEmoji = getStageEmoji(event.status);
	const date = event.date ? new Date(event.date).toLocaleDateString() : 'TBD';
	
	return `${typeEmoji} **${event.title}**\n` +
		`   ${stageEmoji} Status: ${event.status}\n` +
		`   📅 Date: ${date}\n` +
		`   👥 Expected: ${event.expectedAttendees || 'TBD'} | Actual: ${event.actualAttendees || 'N/A'}`;
}

/**
 * Format events list
 * @param {Array} events - Array of events
 * @param {string} groupBy - How to group events ('status', 'date', 'none')
 * @returns {string} - Formatted string
 */
function formatEventsList(events, groupBy = 'status') {
	if (events.length === 0) {
		return 'No events found.';
	}

	if (groupBy === 'status') {
		let output = '';
		for (const stage of EVENT_STAGES) {
			const stageEvents = events.filter(e => e.status === stage);
			if (stageEvents.length > 0) {
				output += `\n${getStageEmoji(stage)} **${stage.toUpperCase()}**\n`;
				output += stageEvents.map(e => formatEventDisplay(e)).join('\n');
				output += '\n';
			}
		}
		return output;
	}

	return events.map(e => formatEventDisplay(e)).join('\n');
}

/**
 * Get events calendar view
 * @param {Array} events - Array of events
 * @returns {string} - Calendar formatted string
 */
function formatCalendarView(events) {
	const sortedEvents = events
		.filter(e => e.date)
		.sort((a, b) => new Date(a.date) - new Date(b.date));

	if (sortedEvents.length === 0) {
		return 'No upcoming events.';
	}

	const lines = [];
	let currentMonth = '';

	for (const event of sortedEvents) {
		const eventDate = new Date(event.date);
		const monthYear = eventDate.toLocaleString('default', { month: 'long', year: 'numeric' });

		if (monthYear !== currentMonth) {
			currentMonth = monthYear;
			lines.push(`\n📅 **${monthYear}**`);
		}

		const day = eventDate.getDate();
		const typeEmoji = getTypeEmoji(event.type);
		const city = event.forkCity || '';

		lines.push(`${day.toString().padStart(2, ' ')} | ${typeEmoji} **${event.title}** ${city ? `(${city})` : ''}`);
	}

	return lines.join('\n');
}

/**
 * Calculate event statistics
 * @param {Array} events - Array of events
 * @returns {Object} - Statistics object
 */
function getEventStats(events) {
	return {
		total: events.length,
		byStage: EVENT_STAGES.reduce((acc, stage) => {
			acc[stage.toLowerCase().replace(' ', '_')] = events.filter(e => e.status === stage).length;
			return acc;
		}, {}),
		byType: EVENT_TYPES.reduce((acc, type) => {
			acc[type] = events.filter(e => e.type?.toLowerCase() === type).length;
			return acc;
		}, {}),
		upcoming: events.filter(e => e.date && new Date(e.date) >= new Date()).length,
		completed: events.filter(e => e.status === 'Completed').length,
	};
}

/**
 * Check if event is upcoming
 * @param {Object} event - Event object
 * @returns {boolean} - True if event is in the future
 */
function isUpcoming(event) {
	if (!event.date) return false;
	return new Date(event.date) >= new Date();
}

/**
 * Check if event is past
 * @param {Object} event - Event object
 * @returns {boolean} - True if event has passed
 */
function isPast(event) {
	if (!event.date) return false;
	return new Date(event.date) < new Date();
}

/**
 * Get days until event
 * @param {Object} event - Event object
 * @returns {number|null} - Days until event or null if no date
 */
function getDaysUntilEvent(event) {
	if (!event.date) return null;
	const eventDate = new Date(event.date);
	const now = new Date();
	return Math.ceil((eventDate - now) / (1000 * 60 * 60 * 24));
}

module.exports = {
	EVENT_STAGES,
	EVENT_TYPES,
	getNextStage,
	getPreviousStage,
	getStageEmoji,
	getTypeEmoji,
	formatEventDisplay,
	formatEventsList,
	formatCalendarView,
	getEventStats,
	isUpcoming,
	isPast,
	getDaysUntilEvent,
};