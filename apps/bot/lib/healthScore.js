/**
 * 🏥 FORK HEALTH SCORING ENGINE
 * Calculates health scores (0-100) based on activity metrics
 */

/**
 * Calculate health score for a fork
 * @param {Object} fork - Fork data from Notion
 * @returns {Object} - { score: number, breakdown: Object }
 */
function calculateHealthScore(fork) {
	const props = fork.properties || {};
	let breakdown = {
		pulseRecency: 0,
		eventsConducted: 0,
		teamCompleteness: 0,
		reportSubmission: 0,
		partnerships: 0,
	};

	// 1. Last Pulse Recency (0-25 points)
	const lastPulse = props['Last Pulse']?.date?.start;
	if (lastPulse) {
		const pulseDate = new Date(lastPulse);
		const now = new Date();
		const diffDays = Math.floor((now - pulseDate) / (1000 * 60 * 60 * 24));

		if (diffDays < 7) {
			breakdown.pulseRecency = 25;
		} else if (diffDays < 30) {
			breakdown.pulseRecency = 15;
		} else if (diffDays < 60) {
			breakdown.pulseRecency = 5;
		}
	}

	// 2. Events Conducted (0-25 points) - 5 pts per event, max 25
	const eventsCount = props['Events Count']?.number || 0;
	breakdown.eventsConducted = Math.min(eventsCount * 5, 25);

	// 3. Team Size Completeness (0-20 points)
	// Based on required roles filled (Tech Lead, Creative Lead, Ops Lead)
	const teamCompleteness = props['Team Completeness']?.number || 0;
	breakdown.teamCompleteness = Math.min(teamCompleteness, 20);

	// 4. Report Submission (0-15 points) - 5 pts per on-time report, max 15
	const reportsSubmitted = props['Reports Submitted']?.number || 0;
	breakdown.reportSubmission = Math.min(reportsSubmitted * 5, 15);

	// 5. Partnerships Secured (0-15 points) - 5 pts per partnership, max 15
	const partnershipsCount = props['Partnerships Count']?.number || 0;
	breakdown.partnerships = Math.min(partnershipsCount * 5, 15);

	const totalScore = Object.values(breakdown).reduce((a, b) => a + b, 0);

	return {
		score: Math.min(totalScore, 100),
		breakdown,
	};
}

/**
 * Get health status label based on score
 * @param {number} score - Health score (0-100)
 * @returns {Object} - { label: string, color: string, emoji: string }
 */
function getHealthStatus(score) {
	if (score >= 80) {
		return { label: 'Excellent', color: '#00FF95', emoji: '💚' };
	} else if (score >= 60) {
		return { label: 'Good', color: '#00F2FF', emoji: '💙' };
	} else if (score >= 40) {
		return { label: 'Fair', color: '#FFCC00', emoji: '💛' };
	} else if (score >= 20) {
		return { label: 'At Risk', color: '#FF9900', emoji: '🧡' };
	} else {
		return { label: 'Critical', color: '#FF0055', emoji: '❤️' };
	}
}

/**
 * Calculate health scores for all forks and rank them
 * @param {Array} forks - Array of fork objects from Notion
 * @returns {Array} - Sorted array of forks with health data
 */
function rankForksByHealth(forks) {
	const forksWithHealth = forks
		.filter(f => f.properties?.Status?.select?.name === 'Active')
		.map(fork => {
			const health = calculateHealthScore(fork);
			const status = getHealthStatus(health.score);
			return {
				fork,
				healthScore: health.score,
				healthBreakdown: health.breakdown,
				healthStatus: status,
			};
		});

	return forksWithHealth.sort((a, b) => b.healthScore - a.healthScore);
}

/**
 * Identify at-risk forks (score below 40)
 * @param {Array} forksWithHealth - Forks with health data
 * @returns {Array} - Forks at risk
 */
function getAtRiskForks(forksWithHealth) {
	return forksWithHealth.filter(f => f.healthScore < 40);
}

/**
 * Get top performing forks
 * @param {Array} forksWithHealth - Forks with health data
 * @param {number} limit - Number of top forks to return
 * @returns {Array} - Top forks
 */
function getTopForks(forksWithHealth, limit = 5) {
	return forksWithHealth.slice(0, limit);
}

module.exports = {
	calculateHealthScore,
	getHealthStatus,
	rankForksByHealth,
	getAtRiskForks,
	getTopForks,
};