export interface StockMetadata {
  ticker: string;
  name: string;
  sector: string;
}

export const VIETNAMESE_STOCKS_METADATA: Record<string, StockMetadata> = {
  // VN30 Constituents
  ACB: { ticker: 'ACB', name: 'Ngân hàng TMCP Á Châu', sector: 'Ngân hàng' },
  BID: { ticker: 'BID', name: 'Ngân hàng TMCP Đầu tư và Phát triển VN', sector: 'Ngân hàng' },
  BSR: { ticker: 'BSR', name: 'CTCP Lọc hóa dầu Bình Sơn', sector: 'Dầu khí' },
  CTG: { ticker: 'CTG', name: 'Ngân hàng TMCP Công Thương Việt Nam', sector: 'Ngân hàng' },
  FPT: { ticker: 'FPT', name: 'Công ty Cổ phần FPT', sector: 'Công nghệ & Viễn thông' },
  GAS: { ticker: 'GAS', name: 'Tổng Công ty Khí Việt Nam', sector: 'Dầu khí' },
  GVR: { ticker: 'GVR', name: 'Tập đoàn Công nghiệp Cao su Việt Nam', sector: 'Cao su & Nông nghiệp' },
  HDB: { ticker: 'HDB', name: 'Ngân hàng TMCP Phát triển TP.HCM', sector: 'Ngân hàng' },
  HPG: { ticker: 'HPG', name: 'CTCP Tập đoàn Hòa Phát', sector: 'Thép & Vật liệu' },
  LPB: { ticker: 'LPB', name: 'Ngân hàng TMCP Lộc Phát Việt Nam', sector: 'Ngân hàng' },
  MBB: { ticker: 'MBB', name: 'Ngân hàng TMCP Quân Đội', sector: 'Ngân hàng' },
  MCH: { ticker: 'MCH', name: 'CTCP Hàng tiêu dùng Masan', sector: 'Thực phẩm & Đồ uống' },
  MSN: { ticker: 'MSN', name: 'CTCP Tập đoàn Masan', sector: 'Tiêu dùng & Bán lẻ' },
  MWG: { ticker: 'MWG', name: 'CTCP Đầu tư Thế Giới Di Động', sector: 'Tiêu dùng & Bán lẻ' },
  SAB: { ticker: 'SAB', name: 'Tổng CTCP Bia - Rượu - Nước giải khát Sài Gòn', sector: 'Thực phẩm & Đồ uống' },
  SHB: { ticker: 'SHB', name: 'Ngân hàng TMCP Sài Gòn - Hà Nội', sector: 'Ngân hàng' },
  SSB: { ticker: 'SSB', name: 'Ngân hàng TMCP Đông Nam Á (SeABank)', sector: 'Ngân hàng' },
  SSI: { ticker: 'SSI', name: 'CTCP Chứng khoán SSI', sector: 'Chứng khoán' },
  STB: { ticker: 'STB', name: 'Ngân hàng TMCP Sài Gòn Thương Tín', sector: 'Ngân hàng' },
  TCB: { ticker: 'TCB', name: 'Ngân hàng TMCP Kỹ Thương Việt Nam', sector: 'Ngân hàng' },
  TCX: { ticker: 'TCX', name: 'CTCP Chứng khoán Kỹ Thương (TCBS)', sector: 'Chứng khoán' },
  VCB: { ticker: 'VCB', name: 'Ngân hàng TMCP Ngoại Thương Việt Nam', sector: 'Ngân hàng' },
  VHM: { ticker: 'VHM', name: 'CTCP Vinhomes', sector: 'Bất động sản' },
  VIB: { ticker: 'VIB', name: 'Ngân hàng TMCP Quốc tế Việt Nam', sector: 'Ngân hàng' },
  VIC: { ticker: 'VIC', name: 'Tập đoàn Vingroup', sector: 'Bất động sản' },
  VJC: { ticker: 'VJC', name: 'CTCP Hàng không Vietjet', sector: 'Hàng không' },
  VNM: { ticker: 'VNM', name: 'CTCP Sữa Việt Nam (Vinamilk)', sector: 'Thực phẩm & Đồ uống' },
  VPB: { ticker: 'VPB', name: 'Ngân hàng TMCP Việt Nam Thịnh Vượng', sector: 'Ngân hàng' },
  VPL: { ticker: 'VPL', name: 'CTCP Vinpearl', sector: 'Bất động sản & Du lịch' },
  VRE: { ticker: 'VRE', name: 'CTCP Vincom Retail', sector: 'Bất động sản' },

  // Popular Active Midcap / Smallcap
  VIX: { ticker: 'VIX', name: 'CTCP Chứng khoán VIX', sector: 'Chứng khoán' },
  DIG: { ticker: 'DIG', name: 'Tổng CTCP Đầu tư Phát triển Xây dựng (DIC Corp)', sector: 'Bất động sản' },
  NVL: { ticker: 'NVL', name: 'CTCP Tập đoàn Đầu tư Địa ốc No Va (Novaland)', sector: 'Bất động sản' },
  PVD: { ticker: 'PVD', name: 'Tổng CTCP Khoan và Dịch vụ Khoan Dầu khí', sector: 'Dầu khí' },
  VND: { ticker: 'VND', name: 'CTCP Chứng khoán VNDIRECT', sector: 'Chứng khoán' },
  KBC: { ticker: 'KBC', name: 'Tổng Công ty Phát triển Đô thị Kinh Bắc', sector: 'Bất động sản KCN' },
  PDR: { ticker: 'PDR', name: 'CTCP Phát triển Bất động sản Phát Đạt', sector: 'Bất động sản' },
  DXG: { ticker: 'DXG', name: 'CTCP Tập đoàn Đất Xanh', sector: 'Bất động sản' },
  HSG: { ticker: 'HSG', name: 'CTCP Tập đoàn Hoa Sen', sector: 'Thép & Vật liệu' },
  NKG: { ticker: 'NKG', name: 'CTCP Thép Nam Kim', sector: 'Thép & Vật liệu' },
  DGC: { ticker: 'DGC', name: 'CTCP Tập đoàn Hóa chất Đức Giang', sector: 'Hóa chất & Cơ bản' },
  BCM: { ticker: 'BCM', name: 'Tổng CTCP Đầu tư và Phát triển Công nghiệp', sector: 'Bất động sản KCN' },
  PLX: { ticker: 'PLX', name: 'Tập đoàn Xăng dầu Việt Nam', sector: 'Dầu khí' },
  TPB: { ticker: 'TPB', name: 'Ngân hàng TMCP Tiên Phong', sector: 'Ngân hàng' },
  VGI: { ticker: 'VGI', name: 'Tổng CTCP Đầu tư Quốc tế Viettel (Viettel Global)', sector: 'Công nghệ & Viễn thông' },
  CTR: { ticker: 'CTR', name: 'Tổng CTCP Công trình Viettel (Viettel Construction)', sector: 'Công nghệ & Viễn thông' },
  VTP: { ticker: 'VTP', name: 'Tổng CTCP Bưu chính Viettel (Viettel Post)', sector: 'Logistics & Vận tải' },
  FRT: { ticker: 'FRT', name: 'CTCP Bán lẻ Kỹ thuật số FPT (FPT Retail / Long Châu)', sector: 'Bán lẻ & Tiêu dùng' },
  DCM: { ticker: 'DCM', name: 'CTCP Phân bón Dầu khí Cà Mau', sector: 'Hóa chất & Phân bón' },
  DPM: { ticker: 'DPM', name: 'Tổng CTCP Phân bón và Hóa chất Dầu khí', sector: 'Hóa chất & Phân bón' },
  REE: { ticker: 'REE', name: 'CTCP Cơ Điện Lạnh', sector: 'Cơ điện & Năng lượng' },
  GEX: { ticker: 'GEX', name: 'CTCP Tập đoàn GELEX', sector: 'Thiết bị điện' },
  HDG: { ticker: 'HDG', name: 'CTCP Tập đoàn Hà Đô', sector: 'Bất động sản' },
  KDH: { ticker: 'KDH', name: 'CTCP Đầu tư và Kinh doanh Nhà Khang Điền', sector: 'Bất động sản' },
  VSC: { ticker: 'VSC', name: 'CTCP Tập đoàn Container Việt Nam', sector: 'Logistics & Cảng biển' },
  HAH: { ticker: 'HAH', name: 'CTCP Vận tải và Xếp dỡ Hải An', sector: 'Logistics & Cảng biển' },
  ANV: { ticker: 'ANV', name: 'CTCP Nam Việt', sector: 'Thủy sản & Nông nghiệp' },
  VHC: { ticker: 'VHC', name: 'CTCP Vĩnh Hoàn', sector: 'Thủy sản & Nông nghiệp' },
  PC1: { ticker: 'PC1', name: 'CTCP Tập đoàn PC1', sector: 'Xây lắp & Năng lượng' },
  SZC: { ticker: 'SZC', name: 'CTCP Sonadezi Châu Đức', sector: 'Bất động sản KCN' },
  IDC: { ticker: 'IDC', name: 'Tổng Công ty IDICO', sector: 'Bất động sản KCN' },
  PVT: { ticker: 'PVT', name: 'Tổng CTCP Vận tải Dầu khí', sector: 'Dầu khí & Vận tải' },
  POW: { ticker: 'POW', name: 'Tổng CTCP Điện lực Dầu khí Việt Nam', sector: 'Năng lượng' },
};

export const POPULAR_QUICK_STOCKS = [
  'VIX', 'DIG', 'NVL', 'DGC', 'PVD', 'VND', 'KBC', 'PDR', 'DXG', 'HSG', 'VGI', 'FRT'
];

export function getStockMetadata(ticker: string): StockMetadata {
  const clean = ticker.trim().toUpperCase();
  if (VIETNAMESE_STOCKS_METADATA[clean]) {
    return VIETNAMESE_STOCKS_METADATA[clean];
  }
  return {
    ticker: clean,
    name: `CTCP ${clean}`,
    sector: 'Cổ phiếu niêm yết'
  };
}
