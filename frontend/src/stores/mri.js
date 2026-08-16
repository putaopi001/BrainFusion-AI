import { defineStore } from "pinia"

export const useMriStore = defineStore("mri", {
  state: () => ({
    mri: null,
    volumeMeta: null,
    status: null,
  }),
  actions: {
    setMri(mri) {
      this.mri = mri
      this.status = mri?.display_status || mri?.status || null
    },
    setVolumeMeta(meta) {
      this.volumeMeta = meta
    },
    clear() {
      this.mri = null
      this.volumeMeta = null
      this.status = null
    },
  },
})
