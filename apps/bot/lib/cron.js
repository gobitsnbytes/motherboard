const cron = require('node-cron');
const Sentry = require('@sentry/node');

// Every scheduled job reports a Sentry cron check-in (monitor auto-created from
// its name), so missed, crashed, or hung runs alert instead of failing silently.
module.exports = process.env.SENTRY_DSN ? Sentry.cron.instrumentNodeCron(cron) : cron;
