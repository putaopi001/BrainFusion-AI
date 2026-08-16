import { defineStore } from "pinia"

export const useReportStore = defineStore("report", {
  state: () => ({
    report: null,
    doctorOpinion: null,
  }),
  actions: {
    setReport(report) {
      this.report = report
    },
    setDoctorOpinion(opinion) {
      this.doctorOpinion = opinion
    },
    clear() {
      this.report = null
      this.doctorOpinion = null
    },
  },
})
