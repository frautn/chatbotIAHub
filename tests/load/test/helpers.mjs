import { readFile } from 'node:fs/promises';

export const example = JSON.parse(await readFile(new URL('../config.example.json', import.meta.url)));

export function config(overrides = {}) {
  return {
    ...structuredClone(example),
    selectors: {
      username: '#username', password: '#password', login: '#loginbtn',
      launch: '#launch', chatInput: '#input', send: '#send',
      busy: '#busy', assistantMessage: '.assistant',
      chatError: '.chat-error',
    },
    ...overrides,
  };
}
