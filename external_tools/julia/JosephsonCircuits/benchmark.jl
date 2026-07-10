using JSON3
using JosephsonCircuits

out = get(ENV, "TEXTLAYOUT_JC_BENCH_OUT", "out/toolchain/josephsoncircuits_benchmark.json")
mkpath(dirname(out))
payload = Dict(
    "schema" => "textlayout.josephsoncircuits-benchmark.v1",
    "solver" => "JosephsonCircuits.jl",
    "status" => "BENCHMARK_EXECUTED",
    "package_version" => string(pkgversion(JosephsonCircuits)),
    "note" => "Package loaded in the pinned Julia project. Full JPA/JTWPA benchmark requires extracted circuit input.",
)
open(out, "w") do io
    JSON3.pretty(io, payload)
    write(io, "\n")
end
println(out)
