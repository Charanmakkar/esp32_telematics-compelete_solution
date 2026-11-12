export const CHANNEL_COUNT = 6;
export const ADC_GPIO = [32, 33, 34, 35, 36, 39] as const;
export const channelMapping = (channel: number) =>
  `GPIO${ADC_GPIO[channel - 1]} · ADC1`;
