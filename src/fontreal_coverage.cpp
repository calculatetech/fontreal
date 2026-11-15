// Selected mask processing. The immutable Python studies are the numerical oracle.
#include "fontreal_coverage.h"

#include <algorithm>
#include <array>
#include <climits>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <memory_resource>
#include <new>
#include <tuple>
#include <vector>

namespace {
using Byte = unsigned char;
template<class T> using Vec = std::pmr::vector<T>;
using Resource = std::pmr::memory_resource;

class Memory final : public Resource {
    FT_Memory owner;
    void *do_allocate(std::size_t bytes, std::size_t alignment) override {
        if (bytes > LONG_MAX || alignment > alignof(std::max_align_t)) throw std::bad_alloc();
        void *p = owner->alloc(owner, static_cast<long>(bytes));
        if (!p) throw std::bad_alloc();
        return p;
    }
    void do_deallocate(void *p, std::size_t, std::size_t) override { owner->free(owner, p); }
    bool do_is_equal(const Resource &other) const noexcept override { return this == &other; }
public:
    explicit Memory(FT_Memory memory) : owner(memory) {}
};

struct Grid {
    const Vec<Byte> &raw;
    int w, h, n;
    int index(int axis, int a, int b) const { return axis ? a*w+b : b*w+a; }
    int value(int x, int y) const { return x>=0 && x<w && y>=0 && y<h ? raw[y*w+x] : 0; }
    int at(int axis, int a, int b) const { return axis ? value(b,a) : value(a,b); }
    template<class F> void neighbors(int i, F f) const {
        int x=i%w, y=i/w;
        for (int yy=std::max(0,y-1); yy<std::min(h,y+2); ++yy)
            for (int xx=std::max(0,x-1); xx<std::min(w,x+2); ++xx)
                if (xx!=x || yy!=y) f(yy*w+xx);
    }
};

int median_round(Vec<int> &values) {
    std::sort(values.begin(), values.end());
    std::size_t middle=values.size()/2;
    return values.size()%2 ? values[middle]
        : static_cast<int>(std::floor((values[middle-1]+values[middle])/2.0+0.5));
}

Vec<Byte> bridge_gain(const Grid &g, Resource *r) {
    Vec<int> labels(g.n,-1,r), pending(r), group(r);
    int label=0;
    for (int i=0; i<g.n; ++i) if (g.raw[i]>=170 && labels[i]<0) {
        labels[i]=label; pending.push_back(i);
        while (!pending.empty()) {
            int p=pending.back(); pending.pop_back();
            g.neighbors(p,[&](int j) { if (g.raw[j]>=170 && labels[j]<0) {
                labels[j]=label; pending.push_back(j);
            }});
        }
        ++label;
    }
    Vec<int> candidates(g.n,-1,r);
    for (int i=0; i<g.n; ++i) if (g.raw[i]>=140 && g.raw[i]<170) {
        std::array<int,8> ring{}; int count=0, components=0, original=-1;
        bool same=true;
        g.neighbors(i,[&](int j) { if (g.raw[j]>=170) {
            ring[count++]=j;
            if (original<0) original=labels[j];
            else if (original!=labels[j]) same=false;
        }});
        std::array<bool,8> seen{};
        for (int a=0; a<count; ++a) if (!seen[a]) {
            ++components; seen[a]=true; pending.push_back(a);
            while (!pending.empty()) {
                int a0=pending.back(); pending.pop_back();
                for (int b=0; b<count; ++b) if (!seen[b] &&
                    std::abs(ring[a0]%g.w-ring[b]%g.w)<=1 &&
                    std::abs(ring[a0]/g.w-ring[b]/g.w)<=1) {
                    seen[b]=true; pending.push_back(b);
                }
            }
        }
        if (components==2 && same) candidates[i]=original;
    }
    Vec<Byte> visited(g.n,0,r), bridge(g.n,0,r);
    for (int i=0; i<g.n; ++i) if (candidates[i]>=0 && !visited[i]) {
        bool same=true; group.clear(); pending.push_back(i); visited[i]=1;
        while (!pending.empty()) {
            int p=pending.back(); pending.pop_back(); group.push_back(p);
            if (candidates[p]!=candidates[i]) same=false;
            g.neighbors(p,[&](int j) { if (candidates[j]>=0 && !visited[j]) {
                visited[j]=1; pending.push_back(j);
            }});
        }
        if (same) for (int p:group) bridge[p]=1;
    }
    Vec<Byte> result(g.raw.begin(),g.raw.end(),r);
    Vec<int> strong_seen(g.n,-1,r);
    std::fill(visited.begin(),visited.end(),0);
    auto weak=[&](int p) { return (g.raw[p]>=170 && g.raw[p]<230) || bridge[p]; };
    for (int i=0; i<g.n; ++i) if (weak(i) && !visited[i]) {
        std::int64_t sum=0, count=0; group.clear(); visited[i]=1; pending.push_back(i);
        while (!pending.empty()) {
            int p=pending.back(); pending.pop_back(); group.push_back(p);
            g.neighbors(p,[&](int j) {
                if (g.raw[j]>=230 && strong_seen[j]!=i) {
                    strong_seen[j]=i; sum+=g.raw[j]; ++count;
                }
                if (weak(j) && !visited[j]) { visited[j]=1; pending.push_back(j); }
            });
        }
        if (count) for (int p:group) result[p]=static_cast<Byte>((2*sum+count)/(2*count));
    }
    for (Byte &v:result) if (v>=128 && v<230)
        v=static_cast<Byte>(std::max<int>(v,std::min(226,(11*v+4)/8)));
    return result;
}

struct Pair { int core, fringe; };
struct Concentration {
    Vec<Pair> pairs;
    explicit Concentration(Resource *r):pairs(r) {}
};

Vec<Byte> strong_winner(const Grid &g, const Vec<Byte> &chosen, Resource *r) {
    Vec<Concentration> runs(r);
    for (int axis=0; axis<2; ++axis) {
        int across=axis?g.h:g.w, along=axis?g.w:g.h;
        for (int a=0; a<across-1; ++a) {
            auto eligible=[&](int b) {
                int x=g.at(axis,a,b), y=g.at(axis,a+1,b);
                return x>0 && y>0 && x+y>=192 && x+y<=384 && std::abs(x-y)>=16 &&
                       std::max(g.at(axis,a-1,b),g.at(axis,a+2,b))<=32;
            };
            for (int start=0; start<along;) {
                if (!eligible(start)) { ++start; continue; }
                int end=start+1;
                while (end<along && eligible(end) &&
                       std::abs(g.at(axis,a,end)-g.at(axis,a,start))<=8 &&
                       std::abs(g.at(axis,a+1,end)-g.at(axis,a+1,start))<=8) ++end;
                if (end-start>=3) {
                    Concentration run(r);
                    for (int b=start; b<end; ++b) {
                        int x=g.index(axis,a,b), y=g.index(axis,a+1,b);
                        run.pairs.push_back(g.raw[x]>g.raw[y] ? Pair{x,y}:Pair{y,x});
                    }
                    runs.push_back(std::move(run));
                }
                start=end;
            }
        }
    }
    Vec<int> counts(g.n,0,r);
    for (const auto &run:runs) for (auto p:run.pairs) { ++counts[p.core]; ++counts[p.fringe]; }
    Vec<Byte> result(chosen.begin(),chosen.end(),r);
    for (const auto &run:runs) {
        if (std::any_of(run.pairs.begin(),run.pairs.end(),[&](Pair p) { return counts[p.core]!=1 || counts[p.fringe]!=1; })) continue;
        for (auto p:run.pairs) {
            int total=g.raw[p.core]+g.raw[p.fringe], peak=std::min(240,total-1);
            if (std::max(chosen[p.core],chosen[p.fringe])<230 && peak>chosen[p.core]) {
                result[p.core]=static_cast<Byte>(peak); result[p.fringe]=static_cast<Byte>(total-peak);
            }
            if (std::max(g.raw[p.core],g.raw[p.fringe])<230 && peak>g.raw[p.core] &&
                chosen[p.core]>=230 && chosen[p.fringe]<230) {
                int rest=total-chosen[p.core];
                if (rest>0 && rest<std::min(chosen[p.core],chosen[p.fringe])) result[p.fringe]=static_cast<Byte>(rest);
            }
        }
    }
    return result;
}

struct Row { int core=0, fringe=0, inner=0; bool valid=false; };
struct Proposal { int index, value; };
struct Anchor { int along, peak, value, core; };
struct Profile {
    int axis, side, across;
    bool valid=true;
    Vec<Proposal> proposals;
    Vec<int> cores;
    Vec<Anchor> anchors;
    explicit Profile(Resource *r):proposals(r),cores(r),anchors(r) {}
};
struct Votes {
    int axis, across, side;
    Vec<Anchor> anchors;
    explicit Votes(Resource *r):anchors(r) {}
};

Vec<Byte> profiles_corners(const Grid &g, const Vec<Byte> &accepted, Resource *r) {
    Vec<Profile> runs(r); Vec<int> median_values(r);
    for (int axis=0; axis<2; ++axis) {
        int across=axis?g.h:g.w, along=axis?g.w:g.h;
        for (int a=0; a<across; ++a) for (int side:{-1,1}) {
            if (a+side<0 || a+side>=across) continue;
            Vec<Row> rows(along,Row{},r);
            for (int b=0; b<along; ++b) {
                int f=g.index(axis,a,b), c=g.index(axis,a+side,b);
                if (g.raw[f]>0 && g.raw[f]<230 && g.raw[c]>0 && g.at(axis,a-side,b)<=32)
                    rows[b]=Row{c,f,g.at(axis,a+2*side,b),true};
            }
            int last_end=-1;
            for (int start=0; start<along-1; ++start) {
                if (!rows[start].valid) continue;
                int lo=g.raw[rows[start].fringe], hi=lo, end=start+1;
                while (end<along && rows[end].valid) {
                    int v=g.raw[rows[end].fringe];
                    if (std::max(hi,v)-std::min(lo,v)>16) break;
                    lo=std::min(lo,v); hi=std::max(hi,v); ++end;
                }
                if (end-start<2 || end<=last_end) continue;
                last_end=end;
                if (end-start==2) {
                    bool supported=true;
                    for (int b:{start-1,end}) {
                        bool strong=false;
                        for (int aa=a+side-1; aa<a+side+2; ++aa) strong|=g.at(axis,aa,b)>=230;
                        supported&=strong;
                    }
                    if (!supported) continue;
                }
                Profile run(r); run.axis=axis; run.side=side; run.across=a+side;
                std::int64_t native_vote=0, chosen_vote=0; median_values.clear();
                for (int b=start; b<end; ++b) {
                    Row p=rows[b]; int total=g.raw[p.core]+g.raw[p.fringe], peak=std::max<int>(240,accepted[p.core]);
                    if (!p.inner && total>=192 && total<=384 && total-peak>0 && total-peak<=accepted[p.fringe]) {
                        run.anchors.push_back({b,peak,total-peak,p.core});
                        median_values.push_back(total-peak-g.raw[p.fringe]);
                        native_vote+=g.raw[p.core]-g.raw[p.fringe]; chosen_vote+=accepted[p.core]-accepted[p.fringe];
                    }
                }
                if (run.anchors.size()<2 || std::make_tuple(native_vote,chosen_vote,side)<std::make_tuple(std::int64_t(0),std::int64_t(0),0)) continue;
                int phase=median_round(median_values); bool changed=false;
                for (int b=start; b<end; ++b) {
                    Row p=rows[b]; int peak=std::max<int>(240,accepted[p.core]), total=g.raw[p.core]+g.raw[p.fringe];
                    auto fixed=std::find_if(run.anchors.begin(),run.anchors.end(),[&](Anchor v) { return v.along==b; });
                    int fringe=fixed!=run.anchors.end() ? fixed->value
                        : std::min({int(accepted[p.fringe]),int(g.raw[p.fringe])+phase,total-peak});
                    if (fringe<=0 || fringe>=peak || peak>=total) continue;
                    run.proposals.push_back({p.core,peak}); run.proposals.push_back({p.fringe,std::min<int>(accepted[p.fringe],fringe)});
                    run.cores.push_back(p.core); changed|=accepted[p.core]!=peak || accepted[p.fringe]!=fringe;
                }
                if (changed) runs.push_back(std::move(run));
            }
        }
    }
    Vec<Byte> axes(g.n,0,r), conflicts(g.n,0,r); Vec<int> values(g.n,-1,r);
    for (const auto &run:runs) for (auto p:run.proposals) axes[p.index]|=static_cast<Byte>(1<<run.axis);
    for (auto &run:runs) for (auto p:run.proposals) if (axes[p.index]==3) run.valid=false;
    for (const auto &run:runs) if (run.valid) for (auto p:run.proposals) {
        if (values[p.index]>=0 && values[p.index]!=p.value) conflicts[p.index]=1;
        values[p.index]=p.value;
    }
    for (auto &run:runs) if (run.valid) for (auto p:run.proposals) if (conflicts[p.index]) run.valid=false;
    Vec<Byte> result(accepted.begin(),accepted.end(),r), cores(g.n,0,r), anchored(g.n,0,r);
    Vec<Votes> votes(r);
    for (const auto &run:runs) if (run.valid) {
        for (auto p:run.proposals) result[p.index]=static_cast<Byte>(p.value);
        for (int c:run.cores) cores[c]=1;
        auto found=std::find_if(votes.begin(),votes.end(),[&](const Votes &v) {
            return v.axis==run.axis && v.across==run.across && v.side==run.side;
        });
        if (found==votes.end()) {
            Votes group(r); group.axis=run.axis; group.across=run.across; group.side=run.side;
            votes.push_back(std::move(group)); found=votes.end()-1;
        }
        for (auto a:run.anchors) { found->anchors.push_back(a); anchored[a.core]=1; }
    }
    for (const auto &group:votes) for (auto first:group.anchors) for (auto last:group.anchors) {
        if (last.along-first.along<2) continue;
        int lo=256, hi=-1; bool stable=true;
        for (int b=first.along; b<=last.along; ++b) {
            int v=g.at(group.axis,group.across,b);
            if (!v || g.at(group.axis,group.across+group.side,b)>32) { stable=false; break; }
            lo=std::min(lo,v); hi=std::max(hi,v);
        }
        if (!stable || hi-lo>16) continue;
        median_values.clear();
        for (auto a:group.anchors) if (a.along>=first.along && a.along<=last.along) median_values.push_back(a.peak);
        int peak=median_round(median_values);
        for (int b=first.along; b<=last.along; ++b) {
            int i=g.index(group.axis,group.across,b);
            if (!anchored[i]) { result[i]=static_cast<Byte>(std::max<int>(result[i],peak)); cores[i]=1; }
        }
    }
    struct Step { int core, fringe, peak, value; };
    Vec<Step> steps(r); Vec<Byte> frozen(result.begin(),result.end(),r);
    std::fill(values.begin(),values.end(),-1); std::fill(conflicts.begin(),conflicts.end(),0);
    auto propose=[&](int i,int v) { if (values[i]>=0 && values[i]!=v) conflicts[i]=1; values[i]=v; };
    for (int axis=0; axis<2; ++axis) {
        int across=axis?g.h:g.w, along=axis?g.w:g.h;
        for (int a=0; a<across-1; ++a) for (int b=1; b<along-1; ++b) {
            int p=g.index(axis,a,b), q=g.index(axis,a+1,b), total=g.raw[p]+g.raw[q];
            if (!g.raw[p] || !g.raw[q] || g.raw[p]>=230 || g.raw[q]>=230 || frozen[p]<230 || frozen[q]<230 ||
                total<192 || total>384 || std::max(g.at(axis,a-1,b),g.at(axis,a+2,b))>32) continue;
            bool supported=true;
            for (int bb:{b-1,b+1}) {
                bool strong=false;
                for (int aa=a-1; aa<a+3; ++aa) strong|=g.at(axis,aa,bb)>=230;
                supported&=strong;
            }
            if (!supported) continue;
            int core=-1;
            for (int c:{p,q}) {
                int aa=axis ? c/g.w:c%g.w; bool connects=true;
                for (int bb:{b-1,b+1}) {
                    bool strong=false;
                    for (int j=aa-1; j<aa+2; ++j) strong|=g.at(axis,j,bb)>=230;
                    connects&=strong;
                }
                if (connects && (core<0 || std::make_tuple(g.raw[c],frozen[c],c)>std::make_tuple(g.raw[core],frozen[core],core))) core=c;
            }
            if (core<0) continue;
            int fringe=core==p?q:p, peak=std::max<int>(240,frozen[core]), value=total-peak;
            if (cores[fringe] || value<=0 || value>=frozen[fringe]) continue;
            steps.push_back({core,fringe,peak,value}); propose(core,peak); propose(fringe,value);
        }
    }
    for (auto p:steps) if (!conflicts[p.core] && !conflicts[p.fringe]) {
        result[p.core]=static_cast<Byte>(p.peak); result[p.fringe]=static_cast<Byte>(p.value); cores[p.core]=1;
    }
    const std::array<Pair,4> directions{{{1,0},{0,1},{-1,0},{0,-1}}};
    for (int i=0; i<g.n; ++i) if (g.raw[i]>0 && g.raw[i]<230 && !cores[i] && result[i]>g.raw[i]) {
        int x=i%g.w,y=i/g.w;
        for (int d=0; d<4; ++d) {
            Pair a=directions[d],b=directions[(d+1)%4];
            if (std::min(g.value(x+a.core,y+a.fringe),g.value(x+b.core,y+b.fringe))>=230 &&
                std::max(g.value(x-a.core,y-a.fringe),g.value(x-b.core,y-b.fringe))<=32) { result[i]=g.raw[i]; break; }
        }
    }
    return result;
}

struct NativeRun { int start,end; std::int64_t area; double center; };
Vec<NativeRun> scan_runs(const Grid &g,int axis,int t,Resource *r) {
    Vec<NativeRun> result(r); int across=axis?g.h:g.w;
    for (int c=0; c<across;) {
        if (!g.at(axis,c,t)) { ++c; continue; }
        int start=c; std::int64_t area=0; long double weighted=0;
        while (c<across && g.at(axis,c,t)) {
            int v=g.at(axis,c,t); area+=v; weighted+=static_cast<long double>(c)*v; ++c;
        }
        result.push_back({start,c,area,static_cast<double>(weighted)/static_cast<double>(area)});
    }
    return result;
}

bool subpixel_strokes(const Grid &g,Resource *r) {
    bool found=false;
    for (int axis=0; axis<2; ++axis) {
        int along=axis?g.w:g.h;
        if (along<3) continue;
        auto line0=scan_runs(g,axis,0,r),line1=scan_runs(g,axis,1,r);
        for (int t=0; t<along-2; ++t) {
            auto line2=scan_runs(g,axis,t+2,r);
            for (auto a:line0) for (auto b:line1) {
                if (std::max(std::abs(a.start-b.start),std::abs(a.end-b.end))>1) continue;
                for (auto c:line2) {
                    if (std::max(std::abs(b.start-c.start),std::abs(b.end-c.end))>1) continue;
                    std::array<std::int64_t,3> area{{a.area,b.area,c.area}}; std::sort(area.begin(),area.end());
                    if (area[2]-area[0]>16) continue;
                    found=true;
                    if (static_cast<double>(area[1])/std::hypot(1.0,(c.center-a.center)/2)>255) return false;
                }
            }
            line0=std::move(line1); line1=std::move(line2);
        }
    }
    return found;
}

Vec<Byte> weighted_stems(const Grid &g,const Vec<Byte> &preferred,Resource *r) {
    Vec<Byte> result(preferred.begin(),preferred.end(),r);
    if (!subpixel_strokes(g,r)) return result;
    struct Lane { Vec<Pair> pairs; explicit Lane(Resource *r):pairs(r) {} };
    Vec<Lane> lanes(r);
    for (int axis=0; axis<2; ++axis) {
        int across=axis?g.h:g.w,along=axis?g.w:g.h;
        for (int c=0; c<across; ++c) for (int direction:{-1,1}) {
            int donor=c+direction;
            if (donor<0 || donor>=across) continue;
            int last_end=-1;
            for (int start=0; start<along; ++start) {
                int end=start,lo=256,hi=-1,weak=0;
                for (; end<along; ++end) {
                    int v=g.at(axis,c,end);
                    if (!v || (v<230 && g.at(axis,c-direction,end)>32)) break;
                    if (v<230) {
                        if (weak && std::max(hi,v)-std::min(lo,v)>16) break;
                        lo=std::min(lo,v); hi=std::max(hi,v); ++weak;
                    }
                }
                if (end==start || end<=last_end) continue;
                last_end=end;
                if (end-start<5 || weak<3) continue;
                int anchors=0; std::int64_t vote=0,chosen=0;
                for (int t=start; t<end; ++t) {
                    int i=g.index(axis,c,t),j=g.index(axis,donor,t),total=g.raw[i]+g.raw[j];
                    if (g.raw[i]>0 && g.raw[i]<230 && g.raw[j]>0 && total>=192 && total<255 && !g.at(axis,donor+direction,t)) {
                        ++anchors; vote+=g.raw[i]-g.raw[j]; chosen+=preferred[i]-preferred[j];
                    }
                }
                if (!anchors) continue;
                if (!vote) vote=chosen;
                if (vote<0 || (!vote && direction>0)) continue;
                Lane lane(r);
                for (int t=start; t<end; ++t) {
                    int i=g.index(axis,c,t),j=g.index(axis,donor,t);
                    if (preferred[i]<230 && g.raw[j]) lane.pairs.push_back({i,j});
                }
                if (!lane.pairs.empty()) lanes.push_back(std::move(lane));
            }
        }
    }
    Vec<std::int64_t> roles(g.n,-1,r); Vec<Byte> conflict(g.n,0,r);
    auto role=[&](int i,int other,int kind) {
        std::int64_t key=2*static_cast<std::int64_t>(other)+kind;
        if (roles[i]>=0 && roles[i]!=key) conflict[i]=1;
        roles[i]=key;
    };
    for (const auto &lane:lanes) for (auto p:lane.pairs) {
        role(p.core,p.fringe,0); if (preferred[p.fringe]<230) role(p.fringe,p.core,1);
    }
    std::array<std::int64_t,256> histogram{}; std::int64_t positive=0;
    for (int v:preferred) if (v) { ++histogram[v]; ++positive; }
    std::int64_t count=0,numerator=0,denominator=0,needed=(positive+3)/4;
    for (int v=255; v>0; --v) {
        count+=histogram[v]; numerator+=v*v*histogram[v]; denominator+=v*histogram[v];
        if (count>=needed) break;
    }
    int target=denominator ? static_cast<int>((2*numerator+denominator)/(2*denominator)):0;
    for (const auto &lane:lanes) {
        bool rejected=false;
        for (auto p:lane.pairs) rejected|=conflict[p.core] || (preferred[p.fringe]<230 && conflict[p.fringe]);
        if (!rejected) for (auto p:lane.pairs) result[p.core]=static_cast<Byte>(std::max<int>(preferred[p.core],target));
    }
    return result;
}
} // namespace

extern "C" int fontreal_selected_coverage(FT_Memory memory, FT_Byte *pixels,
                                         FT_UInt width, FT_UInt rows, FT_Int pitch) {
    if (!width || !rows) return 0;
    if (!memory || !memory->alloc || !memory->free || !pixels ||
        width>INT_MAX || rows>INT_MAX || std::uint64_t(width)*rows>INT_MAX ||
        (pitch>=0 ? std::int64_t(pitch):-std::int64_t(pitch))<width) return 2;
    try {
        Memory resource(memory); int count=static_cast<int>(width*rows);
        Vec<Byte> raw(count,0,&resource);
        for (unsigned y=0; y<rows; ++y)
            std::copy_n(pixels+static_cast<std::ptrdiff_t>(y)*pitch,width,raw.data()+y*width);
        Grid grid{raw,static_cast<int>(width),static_cast<int>(rows),count};
        auto gained=bridge_gain(grid,&resource);
        auto winner=strong_winner(grid,gained,&resource);
        auto corners=profiles_corners(grid,winner,&resource);
        auto output=weighted_stems(grid,corners,&resource);
        for (unsigned y=0; y<rows; ++y)
            std::copy_n(output.data()+y*width,width,pixels+static_cast<std::ptrdiff_t>(y)*pitch);
        return 0;
    } catch (...) {
        return 1;
    }
}
