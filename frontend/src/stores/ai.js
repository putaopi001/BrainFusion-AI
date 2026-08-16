import { defineStore } from "pinia"

export const useAiStore = defineStore("ai", {
  state: () => ({
    prediction: null,
  }),
  actions: {
    setPrediction(prediction) {
      this.prediction = prediction
    },
    clear() {
      this.prediction = null
    },
  },
})
