# Minimal structural fixture for apply_textlayout_local_patch_to_fastercap_cmakelists.
# This is not a vendored FasterCap build file and is never used to build a solver.

# In this case, we pass the options `wx-config --version=3.0 --static=no --debug`,
set(wxWidgets_CONFIG_OPTIONS --version=3.0 --static=no $<$<CONFIG:Debug>:--debug>)
set(WXWIDGETS_LIBS ${WXWIDGETS_LIBS} ${wxWidgets_LIBRARIES})
target_link_libraries(FasterCap ${EXTRA_LIBS} ${WXWIDGETS_LIBS} ${EIGEN_LIBS} ${wxWidgets_LIBRARIES})
