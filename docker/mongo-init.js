/**
 * EasyCaptcha — MongoDB Initialization Script
 * ============================================
 * Runs ONCE when the MongoDB container is first created (via
 * /docker-entrypoint-initdb.d/). Creates a limited-privilege service
 * account for the EasyCaptcha application.
 *
 * The root admin user is created automatically by
 * MONGO_INITDB_ROOT_USERNAME / MONGO_INITDB_ROOT_PASSWORD.
 * This script adds a second user — "captcha_svc" — that has only
 * readWrite access to the easycaptcha database.
 *
 * Principle of least privilege: the running app never needs the root password.
 */

const captchaPassword = process.env['MONGO_CAPTCHA_PASSWORD'] || 'change-me-in-production';

db = db.getSiblingDB('easycaptcha');

db.createUser({
  user: 'captcha_svc',
  pwd:  captchaPassword,
  roles: [
    { role: 'readWrite', db: 'easycaptcha' },
  ],
});

print('[EasyCaptcha] captcha_svc user created on easycaptcha database.');
print('[EasyCaptcha] MongoDB authentication configured successfully.');
