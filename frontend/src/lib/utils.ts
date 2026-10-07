import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Merges item size/weight into item name without duplicate inputs or duplicate values.
 * Example:
 * itemName: 'C2 AMLA HAIR OIL', size: '51 ML' -> 'C2 AMLA HAIR OIL 51ML'
 * Preserves original size/weight values accurately across ML, L, GM, KG, etc.
 */
export function mergeSizeIntoItemName(itemName: string, size?: string | null): string {
  if (!itemName) return '';
  if (!size || !size.trim() || size.trim() === '0' || size.trim() === 'null' || size.trim() === 'None') {
    return itemName.trim();
  }
  const cleanSize = size.trim();
  const match = cleanSize.match(/^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$/);
  if (match) {
    const numPart = match[1];
    const unitPart = match[2].toUpperCase();
    const formattedSize = `${numPart}${unitPart}`;
    const regex = new RegExp(`\\b${numPart}\\s*${unitPart}\\b`, 'i');
    if (regex.test(itemName)) {
      return itemName.trim();
    }
    return `${itemName.trim()} ${formattedSize}`.trim();
  }
  const escaped = cleanSize.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const rawRegex = new RegExp(`\\b${escaped}\\b`, 'i');
  if (rawRegex.test(itemName)) {
    return itemName.trim();
  }
  return `${itemName.trim()} ${cleanSize}`.trim();
}

