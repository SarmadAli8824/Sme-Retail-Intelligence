const publicDemo=process.env.NEXT_PUBLIC_DEMO === 'true';
export default {
  ...(publicDemo ? {output:'export',basePath:process.env.DEMO_BASE_PATH||'',trailingSlash:true} : {}),
};
