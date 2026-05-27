import { create } from "zustand";

interface ModelSettings {
  id: string;
  provider: string;
  modelName: string | null;
  isActive: boolean;
}

interface UserStore {
  models: ModelSettings[];
  setModels: (m: ModelSettings[]) => void;
}

export const useUserStore = create<UserStore>((set) => ({
  models: [],
  setModels: (models) => set({ models }),
}));
