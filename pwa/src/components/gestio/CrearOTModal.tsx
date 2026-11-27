"use client";

import React from "react";
import { Fulla360OTModal } from "@/components/gestio/Fulla360OTModal";

interface CrearOTModalProps {
  onClose: () => void;
  onSuccess?: (result?: { id: string; codi?: string }) => void;
  initialClientId?: string;
}

/**
 * Wrapper unificat sobre l'únic model de Fulla 360° d'OT (mode="CREATE").
 */
export function CrearOTModal({ onClose, onSuccess, initialClientId }: CrearOTModalProps) {
  return (
    <Fulla360OTModal
      mode="CREATE"
      isOpen={true}
      initialClientId={initialClientId}
      onClose={onClose}
      onSuccess={(res) => onSuccess?.(res)}
    />
  );
}
