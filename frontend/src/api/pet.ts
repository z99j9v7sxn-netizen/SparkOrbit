import { apiGet, apiPost } from './client';

export interface PetAction {
  key: string;
  label: string;
  icon: string;
  animation_row: number;
  frame_count: number;
  fps: number;
  loop: boolean;
  route: string;
}

export interface PetManifest {
  slug: string;
  name: string;
  description: string;
  preview_url: string;
  manifest_url: string;
  sprite_url: string;
  format?: string;
  columns: number;
  rows: number;
  cell_width?: number;
  cell_height?: number;
  sheet_width?: number;
  sheet_height?: number;
  animation_row?: number;
  frame_count: number;
  fps: number;
  actions?: PetAction[];
}

export interface PetAffinity {
  pet_affinity: number;
  level: number;
  level_name: string;
}

export const fetchPets = () => apiGet<PetManifest[]>('/api/pets');
export const fetchOwnedPets = () => apiGet<{ owned: string[] }>('/api/pets/owned');
export const selectPet = (pet_slug: string) =>
  apiPost<{ pet_slug: string; pet_affinity?: number }>('/api/users/me/pet', { pet_slug });
export const bumpPetAffinity = (delta = 1, reason = '') =>
  apiPost<PetAffinity>('/api/pets/affinity', { delta, reason });
export const fetchPetAffinity = () => apiGet<PetAffinity>('/api/pets/affinity');

/** 免费桌宠（与后端 FREE_PET_SLUGS 保持一致） */
export const FREE_PET_SLUGS = ['boxcat', 'mallow', 'ghost', 'guami', 'pupu'] as const;
export const DEFAULT_PET_SLUG = 'boxcat';
