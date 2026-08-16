import { defineStore } from "pinia"

export const useCaseStore = defineStore("case", {
  state: () => ({
    currentCaseId: null,
    currentCase: null,
    currentPatient: null,
  }),
  getters: {
    caseLabel: (state) => (state.currentCase ? "病例 #" + state.currentCase.id : "未选择病例"),
  },
  actions: {
    setCurrentCase(caseId, detail) {
      this.currentCaseId = caseId
      this.currentCase = detail?.case || null
      this.currentPatient = detail?.patient || null
    },
    clear() {
      this.currentCaseId = null
      this.currentCase = null
      this.currentPatient = null
    },
  },
})
