/**
 * Centralized Unit of Measurement (UOM) and Quantity Conversion System for Frontend.
 * Ensures the review table, mapping state, and XML generation all share the exact same conversion logic.
 */

export const UNIT_ALIASES: Record<string, string> = {
  // Dozens
  DZ: 'DOZEN',
  DZN: 'DOZEN',
  DOZ: 'DOZEN',
  DOZEN: 'DOZEN',
  DOZENS: 'DOZEN',
  'DZ.': 'DOZEN',
  'DZN.': 'DOZEN',
  // Pieces / Numbers
  PCS: 'PCS',
  PC: 'PCS',
  PIECE: 'PCS',
  PIECES: 'PCS',
  NOS: 'NOS',
  NO: 'NOS',
  NUM: 'NOS',
  NUMBER: 'NOS',
  NUMBERS: 'NOS',
  // Box / Carton / Case / Packets
  BOX: 'BOX',
  BOXES: 'BOX',
  BX: 'BOX',
  CTN: 'CTN',
  CARTON: 'CTN',
  CARTONS: 'CTN',
  CASE: 'CASE',
  CASES: 'CASE',
  CS: 'CASE',
  PKT: 'PKT',
  PKTS: 'PKT',
  PACKET: 'PKT',
  PACKETS: 'PKT',
  BAG: 'BAG',
  BAGS: 'BAG',
  BG: 'BAG',
  BOTTLE: 'BOTTLE',
  BOTTLES: 'BOTTLE',
  BTL: 'BOTTLE',
  CAN: 'CAN',
  CANS: 'CAN',
  SET: 'SET',
  SETS: 'SET',
  PAIR: 'PAIR',
  PAIRS: 'PAIR',
  ROLL: 'ROLL',
  ROLLS: 'ROLL',
  // Weight
  KG: 'KGS',
  KGS: 'KGS',
  KILOGRAM: 'KGS',
  KILOGRAMS: 'KGS',
  GM: 'GMS',
  GMS: 'GMS',
  GRAM: 'GMS',
  GRAMS: 'GMS',
  // Volume
  LTR: 'LTR',
  LTRS: 'LTR',
  LITRE: 'LTR',
  LITRES: 'LTR',
  LITER: 'LTR',
  ML: 'ML',
  MILLILITRE: 'ML',
  // Length
  MTR: 'MTR',
  MTRS: 'MTR',
  METER: 'MTR',
  METERS: 'MTR',
};

export function normalizeUom(uom?: string | null): string {
  if (!uom) return 'NOS';
  const clean = uom.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  return UNIT_ALIASES[clean] || clean || 'NOS';
}

export interface UnitConversionResult {
  finalQuantity: number;
  finalRate: number;
  finalUom: string;
  conversionFactor?: number;
  conversionNote?: string;
  needsReview: boolean;
}

export function convertQuantityAndRate(
  invoiceQty: number,
  invoiceUom: string,
  targetTallyUom: string,
  invoiceRate: number = 0
): UnitConversionResult {
  const normFrom = normalizeUom(invoiceUom);
  const normTo = normalizeUom(targetTallyUom);

  // STRICT PRD REQUIREMENT:
  // Stock Items imported from Tally are the SOLE SOURCE OF TRUTH for UOM.
  // NO FALSE MATHEMATICAL CONVERSIONS: e.g. 2 Doz with Tally unit DZN remains Qty = 2, UOM = DZN.
  // Never convert to 24 PCS. The invoice quantity is strictly preserved.
  const note = normFrom !== normTo
    ? `Mapped invoice unit '${invoiceUom}' to Tally unit '${targetTallyUom}'`
    : undefined;

  return {
    finalQuantity: invoiceQty,
    finalRate: invoiceRate,
    finalUom: targetTallyUom,
    conversionFactor: 1.0,
    conversionNote: note,
    needsReview: false,
  };
}
