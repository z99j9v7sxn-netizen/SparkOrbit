declare module '@avatar-sdk' {
  export enum SDKEvents {
    connected = 'connected',
    disconnected = 'disconnected',
    error = 'error',
    frame_start = 'frame_start',
    frame_stop = 'frame_stop',
    stream_start = 'stream_start',
  }
  export enum PlayerEvents {
    play = 'play',
    playNotAllowed = 'not-allowed',
    error = 'error',
  }
  export default class AvatarPlatform {
    constructor(props?: { useInlinePlayer?: boolean });
    setApiInfo(info: Record<string, unknown>): this;
    setGlobalParams(config: Record<string, unknown>): this;
    start(props?: { wrapper?: HTMLDivElement }): Promise<void>;
    writeText(text: string, extend?: Record<string, unknown>): Promise<string>;
    interrupt(): Promise<void>;
    stop(): void;
    destroy(): void;
    createPlayer(): {
      resume?: () => Promise<void>;
      on?: (t: string, fn: (...a: unknown[]) => void) => void;
    };
    on(type: string, listener: (...args: unknown[]) => void): this;
    get player(): {
      resume?: () => Promise<void>;
      on?: (t: string, fn: (...a: unknown[]) => void) => void;
    } | undefined;
  }
}
