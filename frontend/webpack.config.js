const webpack = require('webpack');

module.exports = {
  resolve: {
    // Point Vue to the complete build version
    alias: {
      'vue$': 'vue/dist/vue.esm-bundler.js'
    }
  },
  plugins: [
    // Define compile-time feature flags
    new webpack.DefinePlugin({
      __VUE_OPTIONS_API__: JSON.stringify(true),
      __VUE_PROD_DEVTOOLS__: JSON.stringify(false),
      __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: JSON.stringify(false)
    })
  ]
}; 