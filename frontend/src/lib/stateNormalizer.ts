/**
 * State Normalizer for Indian GST & Tally (Client-Side).
 * PRD Addendum 1 Part 1: Always outputs full canonical Tally state name.
 */

export const TALLY_STATE_TABLE: Record<string, string> = {
  '01': 'Jammu & Kashmir',
  '02': 'Himachal Pradesh',
  '03': 'Punjab',
  '04': 'Chandigarh',
  '05': 'Uttarakhand',
  '06': 'Haryana',
  '07': 'Delhi',
  '08': 'Rajasthan',
  '09': 'Uttar Pradesh',
  '10': 'Bihar',
  '11': 'Sikkim',
  '12': 'Arunachal Pradesh',
  '13': 'Nagaland',
  '14': 'Manipur',
  '15': 'Mizoram',
  '16': 'Tripura',
  '17': 'Meghalaya',
  '18': 'Assam',
  '19': 'West Bengal',
  '20': 'Jharkhand',
  '21': 'Odisha',
  '22': 'Chhattisgarh',
  '23': 'Madhya Pradesh',
  '24': 'Gujarat',
  '25': 'Dadra & Nagar Haveli and Daman & Diu',
  '26': 'Dadra & Nagar Haveli and Daman & Diu',
  '27': 'Maharashtra',
  '29': 'Karnataka',
  '30': 'Goa',
  '31': 'Lakshadweep',
  '32': 'Kerala',
  '33': 'Tamil Nadu',
  '34': 'Puducherry',
  '35': 'Andaman & Nicobar Islands',
  '36': 'Telangana',
  '37': 'Andhra Pradesh',
  '38': 'Ladakh',
  '97': 'Other Territory',
};

const STATE_ALIASES: Record<string, string> = {
  '01': '01', 'JK': '01', 'J&K': '01', 'JAMMU': '01', 'KASHMIR': '01', 'JAMMU & KASHMIR': '01', 'JAMMU AND KASHMIR': '01',
  '02': '02', 'HP': '02', 'H P': '02', 'HIMACHAL': '02', 'HIMACHAL PRADESH': '02', 'H PRADESH': '02', 'HPRADESH': '02',
  '03': '03', 'PB': '03', 'PUNJAB': '03', 'PUN': '03',
  '04': '04', 'CH': '04', 'CHD': '04', 'CHANDIGARH': '04',
  '05': '05', 'UK': '05', 'UA': '05', 'UTTARAKHAND': '05', 'UTTARANCHAL': '05',
  '06': '06', 'HR': '06', 'HARYANA': '06',
  '07': '07', 'DL': '07', 'DELHI': '07', 'NEW DELHI': '07', 'NCT OF DELHI': '07',
  '08': '08', 'RJ': '08', 'RAJASTHAN': '08',
  '09': '09', 'UP': '09', 'UTTAR PRADESH': '09', 'U PRADESH': '09',
  '10': '10', 'BR': '10', 'BIHAR': '10',
  '11': '11', 'SK': '11', 'SIKKIM': '11',
  '12': '12', 'AR': '12', 'ARUNACHAL': '12', 'ARUNACHAL PRADESH': '12',
  '13': '13', 'NL': '13', 'NAGALAND': '13',
  '14': '14', 'MN': '14', 'MANIPUR': '14',
  '15': '15', 'MZ': '15', 'MIZORAM': '15',
  '16': '16', 'TR': '16', 'TRIPURA': '16',
  '17': '17', 'ML': '17', 'MEGHALAYA': '17',
  '18': '18', 'AS': '18', 'ASSAM': '18',
  '19': '19', 'WB': '19', 'WEST BENGAL': '19',
  '20': '20', 'JH': '20', 'JHARKHAND': '20',
  '21': '21', 'OR': '21', 'OD': '21', 'ODISHA': '21', 'ORISSA': '21',
  '22': '22', 'CG': '22', 'CT': '22', 'CHHATTISGARH': '22',
  '23': '23', 'MP': '23', 'MADHYA PRADESH': '23',
  '24': '24', 'GJ': '24', 'GUJARAT': '24',
  '25': '26', '26': '26', 'DN': '26', 'DD': '26', 'DAMAN': '26', 'DIU': '26', 'DADRA': '26', 'DADRA & NAGAR HAVELI AND DAMAN & DIU': '26',
  '27': '27', 'MH': '27', 'MAHARASHTRA': '27',
  '29': '29', 'KA': '29', 'KARNATAKA': '29',
  '30': '30', 'GA': '30', 'GOA': '30',
  '31': '31', 'LD': '31', 'LAKSHADWEEP': '31',
  '32': '32', 'KL': '32', 'KERALA': '32',
  '33': '33', 'TN': '33', 'TAMIL NADU': '33',
  '34': '34', 'PY': '34', 'PUDUCHERRY': '34', 'PONDICHERRY': '34',
  '35': '35', 'AN': '35', 'ANDAMAN': '35', 'ANDAMAN & NICOBAR ISLANDS': '35',
  '36': '36', 'TS': '36', 'TG': '36', 'TELANGANA': '36',
  '37': '37', 'AP': '37', 'ANDHRA PRADESH': '37',
  '38': '38', 'LA': '38', 'LADAKH': '38',
  '97': '97', 'OT': '97', 'OTHER TERRITORY': '97',
};

export function cleanStateText(raw?: string | null): string {
  if (!raw) return '';
  return raw
    .toString()
    .trim()
    .toUpperCase()
    .replace(/[\.,\-:/\(\)\[\]]/g, ' ')
    .replace(/\b(STATE|CODE|NAME|NO)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function normalizeState(raw?: string | null): { name: string; code: string } | null {
  if (!raw) return null;
  const rawStr = raw.toString().trim();
  if (!rawStr) return null;

  // Direct 2-digit code check
  const codeMatch = rawStr.match(/\b(0[1-9]|[1-2][0-9]|3[0-8]|97)\b/);
  if (codeMatch) {
    const code = codeMatch[1];
    const name = TALLY_STATE_TABLE[code];
    if (name) {
      const cleaned = cleanStateText(rawStr);
      if (cleaned === code || !cleaned) {
        return { name, code };
      }
    }
  }

  const cleaned = cleanStateText(rawStr);
  if (!cleaned) {
    if (codeMatch) {
      const code = codeMatch[1];
      return { name: TALLY_STATE_TABLE[code] || '', code };
    }
    return null;
  }

  if (STATE_ALIASES[cleaned]) {
    const code = STATE_ALIASES[cleaned];
    return { name: TALLY_STATE_TABLE[code] || '', code };
  }

  const noSpace = cleaned.replace(/\s+/g, '');
  if (STATE_ALIASES[noSpace]) {
    const code = STATE_ALIASES[noSpace];
    return { name: TALLY_STATE_TABLE[code] || '', code };
  }

  if (codeMatch) {
    const code = codeMatch[1];
    const name = TALLY_STATE_TABLE[code];
    if (name) return { name, code };
  }

  // Substring alias match
  const aliases = Object.keys(STATE_ALIASES).sort((a, b) => b.length - a.length);
  for (const alias of aliases) {
    if (alias.length >= 3 && cleaned.includes(alias)) {
      const code = STATE_ALIASES[alias];
      return { name: TALLY_STATE_TABLE[code] || '', code };
    }
  }

  return null;
}
