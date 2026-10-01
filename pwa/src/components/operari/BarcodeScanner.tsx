'use client';

import React, { useState } from 'react';

interface BarcodeScannerProps {
    onScan: (barcode: string) => void;
    placeholder?: string;
}

export function BarcodeScanner({ onScan, placeholder = "Introdueix codi de barres..." }: BarcodeScannerProps) {
    const [barcode, setBarcode] = useState('');

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            if (barcode.trim()) {
                onScan(barcode.trim());
                setBarcode('');
            }
        }
    };

    return (
        <div className="w-full flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Escàner de Barcodes</label>
            <div className="relative flex">
                <input
                    type="text"
                    value={barcode}
                    onChange={(e) => setBarcode(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    className="flex-1 p-3 border rounded-l-md shadow-sm focus:ring-2 focus:ring-[--color-primary] focus:border-[--color-primary] bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-white"
                />
                <button
                    onClick={() => {
                        if (barcode.trim()) {
                            onScan(barcode.trim());
                            setBarcode('');
                        }
                    }}
                    className="p-3 bg-[--color-primary] text-white rounded-r-md text-sm hover:bg-opacity-90 transition-colors"
                    type="button"
                >
                    Scan
                </button>
            </div>
            <p className="text-xs text-gray-500">Introdueix el codi de barres manualment o amb un lector extern.</p>
        </div>
    );
}
