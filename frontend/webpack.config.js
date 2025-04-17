const webpack = require('webpack');

module.exports = {
  resolve: {
    // 将Vue指向完整的构建版本
    alias: {
      'vue$': 'vue/dist/vue.esm-bundler.js'
    }
  },
  plugins: [
    // 定义编译时特性标志
    new webpack.DefinePlugin({
      __VUE_OPTIONS_API__: JSON.stringify(true),
      __VUE_PROD_DEVTOOLS__: JSON.stringify(false),
      __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: JSON.stringify(false)
    })
  ]
}; 