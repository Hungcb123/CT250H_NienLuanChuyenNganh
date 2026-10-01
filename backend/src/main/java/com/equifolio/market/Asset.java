package com.equifolio.market;

import jakarta.persistence.*;

@Entity
@Table(name = "assets")
public class Asset {

    @Id
    @Column(length = 32)
    private String ticker; // 'VND', 'HPG', 'VCB', 'GOLD_SJC'

    @Column(nullable = false, length = 100)
    private String name;

    @Column(name = "asset_class", nullable = false, length = 32)
    private String assetClass; // 'CASH', 'STOCK', 'GOLD', 'SAVINGS'

    public Asset() {}

    public Asset(String ticker, String name, String assetClass) {
        this.ticker = ticker;
        this.name = name;
        this.assetClass = assetClass;
    }

    public String getTicker() { return ticker; }
    public void setTicker(String ticker) { this.ticker = ticker; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getAssetClass() { return assetClass; }
    public void setAssetClass(String assetClass) { this.assetClass = assetClass; }
}
