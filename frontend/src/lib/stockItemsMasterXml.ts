/**
 * Tally Stock Items Master XML Generator & Company Profile Manager
 * Strictly conforms to Tally Prime Master export format ('stock items list sample.xml').
 */

export interface LineItemForMaster {
  item_name?: string;
  name?: string;
  hsn_sac?: string;
  hsn?: string;
  uom?: string;
  base_units?: string;
  gst_pct?: number;
  gst_rate?: number;
  cgst_rate?: number;
  sgst_rate?: number;
  igst_rate?: number;
  group?: string;
  parent_group?: string;
}

export interface CompanyProfile {
  id: string;
  name: string;
  gstin: string;
  state: string;
  address: string;
  isDefault?: boolean;
}

export const PRESET_COMPANY_PROFILES: CompanyProfile[] = [];

const STORAGE_KEY_COMPANIES = 'kh_saved_company_profiles';

export function getCompanyProfiles(): CompanyProfile[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY_COMPANIES);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch (e) {
    return [];
  }
}

export function saveCompanyProfile(profile: Omit<CompanyProfile, 'id'>): CompanyProfile {
  const current = getCompanyProfiles();
  const newProfile: CompanyProfile = {
    ...profile,
    id: `custom-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
  };
  const updated = [...current, newProfile];
  if (typeof window !== 'undefined') {
    localStorage.setItem(STORAGE_KEY_COMPANIES, JSON.stringify(updated));
  }
  return newProfile;
}

export const UQC_MAPPING: Record<string, string> = {
  BAG: 'BAG-BAGS',
  BAGS: 'BAG-BAGS',
  BOX: 'BOX-BOX',
  BOXES: 'BOX-BOX',
  BTL: 'BTL-BOTTLES',
  BOTTLE: 'BTL-BOTTLES',
  BOTTLES: 'BTL-BOTTLES',
  CAN: 'PCS-PIECES',
  CANS: 'PCS-PIECES',
  CASE: 'PCS-PIECES',
  CASES: 'PCS-PIECES',
  CRATE: 'BOX-BOX',
  CTN: 'CTN-CARTONS',
  CARTON: 'CTN-CARTONS',
  CARTONS: 'CTN-CARTONS',
  DOZ: 'DOZ-DOZENS',
  DOZEN: 'DOZ-DOZENS',
  DZN: 'DOZ-DOZENS',
  GM: 'GMS-GRAMMES',
  GMS: 'GMS-GRAMMES',
  GRAM: 'GMS-GRAMMES',
  GRAMS: 'GMS-GRAMMES',
  HANGER: 'BOX-BOX',
  HRS: 'BOX-BOX',
  KG: 'KGS-KILOGRAMS',
  KGS: 'KGS-KILOGRAMS',
  KILOGRAM: 'KGS-KILOGRAMS',
  LARI: 'PAC-PACKS',
  LTR: 'LTR-LITRES',
  LTRS: 'LTR-LITRES',
  ML: 'MLT-MILILITRE',
  MLT: 'MLT-MILILITRE',
  MTR: 'MTR-METERS',
  NAG: 'NOS-NUMBERS',
  NOS: 'NOS-NUMBERS',
  NO: 'NOS-NUMBERS',
  PAC: 'PAC-PACKS',
  PACK: 'PAC-PACKS',
  PACKS: 'PAC-PACKS',
  PATTA: 'PAC-PACKS',
  PCS: 'PCS-PIECES',
  PIECES: 'PCS-PIECES',
  PKT: 'PAC-PACKS',
  POUCH: 'PCS-PIECES',
  QTL: 'QTL-QUINTAL',
  ROLL: 'ROL-ROLLS',
  SET: 'SET-SETS',
  SQF: 'SQF-SQUARE FEET',
  SQM: 'SQM-SQUARE METERS',
  TBS: 'TBS-TABLETS',
  TIN: 'PCS-PIECES',
  TON: 'TON-TONNES',
  TREE: 'BOX-BOX',
  TUB: 'TUB-TUBES',
  UNT: 'UNT-UNITS',
  UNIT: 'UNT-UNITS',
  UNITS: 'UNT-UNITS',
  YDS: 'YDS-YARDS',
};

function escapeXml(unsafe: string | null | undefined): string {
  if (!unsafe) return '';
  return String(unsafe)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * Generates an All Masters Tally XML containing <UNIT> and <STOCKITEM> tags
 * strictly conforming to 'stock items list sample.xml'.
 */
export function generateStockItemsMasterXml(
  companyName: string,
  items: LineItemForMaster[],
  defaultParent = 'Primary'
): string {
  const cName = escapeXml(companyName.trim() || 'Kartar Singh & Sons - (from 1-Apr-25)');

  const lines: string[] = [
    '<ENVELOPE>',
    ' <HEADER>',
    '  <TALLYREQUEST>Import Data</TALLYREQUEST>',
    ' </HEADER>',
    ' <BODY>',
    '  <IMPORTDATA>',
    '   <REQUESTDESC>',
    '    <REPORTNAME>All Masters</REPORTNAME>',
    '    <STATICVARIABLES>',
    `     <SVCURRENTCOMPANY>${cName}</SVCURRENTCOMPANY>`,
    '    </STATICVARIABLES>',
    '   </REQUESTDESC>',
    '   <REQUESTDATA>',
  ];

  // 1. Collect unique units
  const uniqueUnits: string[] = [];
  const unitsSeen = new Set<string>();

  for (const it of items) {
    const rawU = (it.uom || it.base_units || 'NOS').trim();
    const uClean = rawU || 'NOS';
    if (!unitsSeen.has(uClean.toUpperCase())) {
      unitsSeen.add(uClean.toUpperCase());
      uniqueUnits.push(uClean);
    }
  }

  for (const u of uniqueUnits) {
    const uEsc = escapeXml(u);
    const uqc = UQC_MAPPING[u.toUpperCase()] || `${u.toUpperCase()}-${u.toUpperCase()}`;
    const uqcEsc = escapeXml(uqc);
    lines.push(
      '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
      `     <UNIT NAME="${uEsc}" RESERVEDNAME="">`,
      `      <NAME>${uEsc}</NAME>`,
      `      <GSTREPUOM>${uqcEsc}</GSTREPUOM>`,
      '      <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>',
      '      <ISDELETED>No</ISDELETED>',
      '      <ISSECURITYONWHENENTERED>No</ISSECURITYONWHENENTERED>',
      '      <ASORIGINAL>Yes</ASORIGINAL>',
      '      <ISGSTEXCLUDED>No</ISGSTEXCLUDED>',
      '      <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>',
      '      <REPORTINGUQCDETAILS.LIST>',
      '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
      `       <REPORTINGUQCNAME>${uqcEsc}</REPORTINGUQCNAME>`,
      '      </REPORTINGUQCDETAILS.LIST>',
      '     </UNIT>',
      '    </TALLYMESSAGE>'
    );
  }

  // 2. Stock items
  const itemsSeen = new Set<string>();
  for (const it of items) {
    const rawName = (it.item_name || it.name || '').trim();
    if (!rawName) continue;
    if (itemsSeen.has(rawName.toUpperCase())) continue;
    itemsSeen.add(rawName.toUpperCase());

    const nameEsc = escapeXml(rawName.replace(/\s+/g, ' '));
    const parentEsc = escapeXml((it.group || it.parent_group || defaultParent).trim());
    const uomEsc = escapeXml((it.uom || it.base_units || 'NOS').trim());
    const hsnRaw = (it.hsn_sac || it.hsn || '').trim();
    const hsnEsc = escapeXml(hsnRaw);

    // Calculate GST Rate
    let gstRate = 0;
    if (it.gst_pct !== undefined && it.gst_pct !== null) {
      gstRate = Number(it.gst_pct);
    } else if (it.gst_rate !== undefined && it.gst_rate !== null) {
      gstRate = Number(it.gst_rate);
    } else if (it.igst_rate) {
      gstRate = Number(it.igst_rate);
    } else if (it.cgst_rate || it.sgst_rate) {
      gstRate = Number(it.cgst_rate || 0) + Number(it.sgst_rate || 0);
    }

    const cgst = (gstRate / 2).toFixed(2);
    const sgst = (gstRate / 2).toFixed(2);
    const igst = gstRate.toFixed(2);

    lines.push(
      '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
      `     <STOCKITEM NAME="${nameEsc}" RESERVEDNAME="" ACTION="Create">`,
      `      <NAME>${nameEsc}</NAME>`,
      `      <PARENT>${parentEsc}</PARENT>`,
      `      <BASEUNITS>${uomEsc}</BASEUNITS>`,
      '      <GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>',
      '      <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>',
      '      <ISCOSTCENTRESON>No</ISCOSTCENTRESON>',
      '      <ISBATCHWISEON>No</ISBATCHWISEON>',
      '      <ISPERISHABLEON>No</ISPERISHABLEON>',
      '      <OPENINGBALANCE>0</OPENINGBALANCE>'
    );

    if (gstRate > 0) {
      lines.push(
        '      <GSTDETAILS.LIST>',
        '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
        '       <CALCULATIONTYPE>On Value</CALCULATIONTYPE>',
        '       <TAXABILITY>Taxable</TAXABILITY>',
        '       <SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>',
        '       <STATEWISEDETAILS.LIST>',
        '        <STATENAME>&#4; Any</STATENAME>',
        '        <RATEDETAILS.LIST>',
        '         <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>',
        '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
        `         <GSTRATE> ${cgst}</GSTRATE>`,
        '        </RATEDETAILS.LIST>',
        '        <RATEDETAILS.LIST>',
        '         <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>',
        '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
        `         <GSTRATE> ${sgst}</GSTRATE>`,
        '        </RATEDETAILS.LIST>',
        '        <RATEDETAILS.LIST>',
        '         <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>',
        '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
        `         <GSTRATE> ${igst}</GSTRATE>`,
        '        </RATEDETAILS.LIST>',
        '       </STATEWISEDETAILS.LIST>',
        '      </GSTDETAILS.LIST>'
      );
    }

    if (hsnEsc) {
      lines.push(
        '      <HSNDETAILS.LIST>',
        '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
        `       <HSNCODE>${hsnEsc}</HSNCODE>`,
        '       <SRCOFHSNDETAILS>Specify Details Here</SRCOFHSNDETAILS>',
        '      </HSNDETAILS.LIST>'
      );
    }

    lines.push('     </STOCKITEM>', '    </TALLYMESSAGE>');
  }

  lines.push('   </REQUESTDATA>', '  </IMPORTDATA>', ' </BODY>', '</ENVELOPE>');

  return lines.join('\n');
}

/**
 * Initiates download of Stock Items Master XML
 */
export async function downloadStockItemsMasterXmlFile(
  companyName: string,
  items: LineItemForMaster[],
  invoiceNumber?: string
): Promise<{ success: boolean; itemCount: number; filename: string }> {
  if (!items || items.length === 0) {
    throw new Error('No items to export.');
  }

  let xmlContent = '';
  const sanitizedInvNo = (invoiceNumber || 'MASTER').replace(/[^a-zA-Z0-9_\-]/g, '_');
  const filename = `Tally_Stock_Items_Master_${sanitizedInvNo}.xml`;

  try {
    // Try backend API first
    const backendUrl = process.env.NEXT_PUBLIC_API_URL
      ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/?$/, '')
      : 'http://localhost:8000';

    const resp = await fetch(`${backendUrl}/api/stock-items/export-master-xml`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: companyName || 'Kartar Singh & Sons - (from 1-Apr-25)',
        items: items.map((it) => ({
          name: it.item_name || it.name,
          hsn: it.hsn_sac || it.hsn,
          uom: it.uom || it.base_units || 'NOS',
          gst_rate: it.gst_pct ?? it.gst_rate ?? 18,
          parent_group: it.group || it.parent_group || 'Primary',
        })),
      }),
    });

    if (resp.ok) {
      const data = await resp.json();
      if (data.xml_content) {
        xmlContent = data.xml_content;
      }
    }
  } catch {
    // Fall back to client generator
  }

  if (!xmlContent) {
    xmlContent = generateStockItemsMasterXml(companyName, items);
  }

  // Trigger browser download
  const blob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  return {
    success: true,
    itemCount: items.length,
    filename,
  };
}
