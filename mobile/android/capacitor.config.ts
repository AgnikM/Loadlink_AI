import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'ai.loadlink.driver',
  appName: 'LoadLink Driver',
  webDir: 'dist',
  bundledWebRuntime: false,
  plugins: {
    LocalNotifications: {
      smallIcon: 'ic_stat_loadlink',
      iconColor: '#2563EB',
      sound: 'beep.wav',
    },
    BackgroundRunner: {
      label: 'ai.loadlink.driver.sync',
      src: 'runners/background-sync.js',
      event: 'syncQueue',
      repeat: true,
      interval: 15,
      autoStart: true,
    },
  },
  android: {
    allowMixedContent: false,
    captureInput: true,
    webContentsDebuggingEnabled: false,
  },
};

export default config;
