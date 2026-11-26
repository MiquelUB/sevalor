"use client";

import React from "react";
import { Feina } from "@/components/gestio/Map";
import { Fulla360OTModal } from "@/components/gestio/Fulla360OTModal";

interface Fulla360OTDrawerProps {
  feina: Feina | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit?: (feinaId: string) => void;
  onFocusMapa?: (feinaId: string) => void;
  onPrefacturaCreated?: () => void;
}

/**
 * Wrapper unificat sobre l'únic model de Fulla 360° d'OT (mode="VIEW_360").
 * Tota l'edició, conciliació i prefacturació conviu dins el mateix model unificat.
 */
export function Fulla360OTDrawer({
  feina,
  isOpen,
  onClose,
  onFocusMapa,
  onPrefacturaCreated,
}: Fulla360OTDrawerProps) {
  if (!isOpen || !feina) return null;
  return (
    <Fulla360OTModal
      mode="VIEW_360"
      isOpen={isOpen}
      feinaId={feina.id}
      initialFeina={feina}
      onClose={onClose}
      onFocusMapa={onFocusMapa}
      onPrefacturaCreated={onPrefacturaCreated}
      onSuccess={() => onPrefacturaCreated?.()}
    />
  );
}
