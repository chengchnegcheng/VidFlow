const electron = require('electron');
console.log('electron:', typeof electron);
console.log('electron.app:', typeof electron.app);

const { app } = require('electron');
console.log('app:', typeof app);

if (app) {
  app.setName('Test');
  console.log('Success!');
  app.quit();
} else {
  console.error('app is undefined!');
  process.exit(1);
}
