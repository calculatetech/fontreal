// Frozen NORMAL D and O/K3 coverage. No font or character identity enters this kernel.
#include "fontreal_v2_coverage.h"

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

struct Pair { int core, fringe; };
struct Concentration {
    Vec<Pair> pairs;
    explicit Concentration(Resource *r):pairs(r) {}
};

Vec<Byte> concentrate(const Grid &g, const Vec<Byte> &chosen, Resource *r) {
    Vec<Concentration> runs(r);
    for (int axis=0; axis<2; ++axis) {
        int across=axis?g.h:g.w, along=axis?g.w:g.h;
        for (int a=0; a<across-1; ++a) {
            auto eligible=[&](int b) {
                int x=g.at(axis,a,b), y=g.at(axis,a+1,b);
                return x>0 && y>0 && x+y>=192 && x+y<=384 &&
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
                        run.pairs.push_back({x,y});
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
        std::int64_t vote=0;
        for (auto p:run.pairs) vote+=g.raw[p.core]-g.raw[p.fringe];
        if (!vote) continue;
        for (auto p:run.pairs) {
            if (vote<0) std::swap(p.core,p.fringe);
            if (std::max(chosen[p.core],chosen[p.fringe])>=230) continue;
            int total=g.raw[p.core]+g.raw[p.fringe], peak=std::min(240,total-1);
            if (peak>chosen[p.core]) {
                result[p.core]=static_cast<Byte>(peak); result[p.fringe]=static_cast<Byte>(total-peak);
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
                if (run.anchors.size()<2 || (!native_vote && !chosen_vote) || std::make_tuple(native_vote,chosen_vote,side)<std::make_tuple(std::int64_t(0),std::int64_t(0),0)) continue;
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

struct Phase { int dx,dy; };
auto phase_key(Phase p) { return std::make_tuple(p.dx*p.dx+p.dy*p.dy,p.dy,p.dx); }

Vec<Byte> overlay(const Vec<Byte> &d, int w, int h, const FT_Bitmap &high,
                  FontrealV2Profile mode, Resource *r) {
    Grid g{d,w,h,static_cast<int>(d.size())};
    std::array<Phase,25> phases{};
    int number=0;
    for (int dy=-2; dy<=2; ++dy) for (int dx=-2; dx<=2; ++dx) phases[number++]={dx,dy};
    Vec<int> sums(static_cast<std::size_t>(g.n)*25,0,r);
    auto sum=[&](int p,int i) { return sums[static_cast<std::size_t>(p)*g.n+i]; };
    for (int p=0; p<25; ++p) for (int y=0; y<h; ++y) for (int x=0; x<w; ++x) {
        int value=0, left=4-phases[p].dx+4*x, top=4-phases[p].dy+4*y;
        for (int yy=top; yy<top+4; ++yy) for (int xx=left; xx<left+4; ++xx)
            value+=high.buffer[static_cast<std::ptrdiff_t>(yy)*high.pitch+xx];
        sums[static_cast<std::size_t>(p)*g.n+y*w+x]=value;
    }
    Vec<int> labels(g.n,-1,r), pending(r), group(r), coherent(g.n,0,r), edge(g.n,0,r), axes(g.n,0,r);
    int label=0;
    for (int i=0; i<g.n; ++i) if (d[i] && labels[i]<0) {
        group.clear(); pending.push_back(i); labels[i]=label;
        while (!pending.empty()) {
            int j=pending.back(); pending.pop_back(); group.push_back(j);
            g.neighbors(j,[&](int k) { if (d[k] && labels[k]<0) { labels[k]=label; pending.push_back(k); }});
        }
        int best=0; std::int64_t maximum=-1;
        for (int p=0; p<25; ++p) {
            std::int64_t score=0;
            for (int j:group) score+=std::int64_t(sum(p,j))*sum(p,j);
            if (score>maximum || (score==maximum && phase_key(phases[p])<phase_key(phases[best]))) { best=p; maximum=score; }
        }
        for (int j:group) coherent[j]=(sum(best,j)+8)/16;
        ++label;
    }
    Vec<Byte> primary(g.n,0,r), local(d.begin(),d.end(),r), fringe(d.begin(),d.end(),r), result(d.begin(),d.end(),r);
    for (int i=0; i<g.n; ++i) if (d[i]) {
        int x=i%w,y=i/w, horizontal=1,vertical=1;
        for (int direction:{-1,1}) {
            for (int j=1; g.value(x+direction*j,y); ++j) ++horizontal;
            for (int j=1; g.value(x,y+direction*j); ++j) ++vertical;
        }
        int axis=horizontal<vertical ? 1:vertical<horizontal ? 2:0;
        axes[i]=axis;
        int best=-1;
        for (int p=0; p<25; ++p) {
            if ((axis==1 && phases[p].dy) || (axis==2 && phases[p].dx)) continue;
            if (best<0 || sum(p,i)>sum(best,i) || (sum(p,i)==sum(best,i) && phase_key(phases[p])<phase_key(phases[best]))) best=p;
        }
        edge[i]=(sum(best,i)+8)/16;
        bool hor=d[i]>=std::max(g.value(x-1,y),g.value(x+1,y)) && d[i]>std::min(g.value(x-1,y),g.value(x+1,y));
        bool ver=d[i]>=std::max(g.value(x,y-1),g.value(x,y+1)) && d[i]>std::min(g.value(x,y-1),g.value(x,y+1));
        primary[i]=d[i]>=128 && ((axis==1 && hor) || (axis==2 && ver) || (!axis && hor && ver));
        if (primary[i]) local[i]=static_cast<Byte>(std::max<int>(d[i],edge[i]));
    }
    fringe=local;
    for (int i=0; i<g.n; ++i) if (primary[i] && local[i]!=d[i])
        g.neighbors(i,[&](int j) {
            if (!primary[j] && d[j]>0 && d[j]<d[i] && edge[j]>d[j]) {
                int value=std::min(edge[j],(2*d[j]*local[i]+d[i])/(2*d[i]));
                fringe[j]=static_cast<Byte>(std::max<int>(fringe[j],value));
            }
        });
    for (int i=0; i<g.n; ++i) if (primary[i]) {
        int reference=coherent[i];
        if (mode==FONTREAL_V2_K3) {
            int best=-1; std::int64_t maximum=-1;
            for (int p=0; p<25; ++p) {
                if ((axes[i]==1 && phases[p].dy) || (axes[i]==2 && phases[p].dx)) continue;
                std::int64_t score=std::int64_t(sum(p,i))*sum(p,i);
                g.neighbors(i,[&](int j) { if (labels[j]==labels[i]) score+=std::int64_t(sum(p,j))*sum(p,j); });
                if (score>maximum || (score==maximum && phase_key(phases[p])<phase_key(phases[best]))) { best=p; maximum=score; }
            }
            reference=(sum(best,i)+8)/16;
        }
        result[i]=static_cast<Byte>(std::max<int>(d[i],reference));
    }
    if (mode==FONTREAL_V2_K3) for (int i=0; i<g.n; ++i) result[i]+=static_cast<Byte>((fringe[i]-local[i]+1)/2);
    return result;
}

bool valid_bitmap(const FT_Bitmap &b) {
    if (b.pixel_mode!=FT_PIXEL_MODE_GRAY || b.num_grays!=256 || b.pitch==INT_MIN) return false;
    if (!b.width || !b.rows) return !b.width && !b.rows;
    std::uint64_t stride=b.pitch<0 ? -std::int64_t(b.pitch):b.pitch;
    if (!b.buffer || stride<b.width || stride*b.rows>PTRDIFF_MAX) return false;
    std::uintptr_t pointer=reinterpret_cast<std::uintptr_t>(b.buffer);
    std::uint64_t offset=stride*(b.rows-1);
    return b.pitch<0 ? pointer>=offset && pointer<=UINTPTR_MAX-b.width
                     : pointer<=UINTPTR_MAX-offset-b.width;
}
} // namespace

#ifdef FONTREAL_V2_OBSERVE_D
extern "C" void fontreal_v2_observe_d(const unsigned char *, unsigned, unsigned);
#endif
extern "C" int fontreal_v2_coverage(FT_Memory memory, FT_Bitmap *raw, const FT_Bitmap *high,
                                    FontrealV2Profile profile) {
    if (!memory || !memory->alloc || !memory->free || !raw || !high ||
        (profile!=FONTREAL_V2_O && profile!=FONTREAL_V2_K3) || !valid_bitmap(*raw) || !valid_bitmap(*high) ||
        raw->width>static_cast<unsigned>(INT_MAX/4-6) || raw->rows>static_cast<unsigned>(INT_MAX/4-6) ||
        high->width!=4*(raw->width+6) || high->rows!=4*(raw->rows+6) ||
        std::uint64_t(raw->width+4)*(raw->rows+4)>INT_MAX ||
        std::uint64_t(raw->width+4)*(raw->rows+4)>SIZE_MAX/(25*sizeof(int))) return 2;
    try {
        Memory resource(memory);
        Vec<Byte> original(static_cast<std::size_t>(raw->width)*raw->rows,0,&resource);
        for (unsigned y=0; y<raw->rows; ++y)
            std::copy_n(raw->buffer+static_cast<std::ptrdiff_t>(y)*raw->pitch,raw->width,original.data()+y*raw->width);
        Grid grid{original,static_cast<int>(raw->width),static_cast<int>(raw->rows),static_cast<int>(original.size())};
        auto fitted=concentrate(grid,original,&resource);
        auto d=profiles_corners(grid,fitted,&resource);
#ifdef FONTREAL_V2_OBSERVE_D
        fontreal_v2_observe_d(d.data(),raw->width,raw->rows);
#endif
        if (original.empty()) return 0;
        int w=static_cast<int>(raw->width)+4,h=static_cast<int>(raw->rows)+4;
        Vec<Byte> padded(static_cast<std::size_t>(w)*h,0,&resource);
        for (unsigned y=0; y<raw->rows; ++y) std::copy_n(d.data()+y*raw->width,raw->width,padded.data()+(y+2)*w+2);
        auto output=overlay(padded,w,h,*high,profile,&resource);
        for (unsigned y=0; y<raw->rows; ++y)
            std::copy_n(output.data()+(y+2)*w+2,raw->width,raw->buffer+static_cast<std::ptrdiff_t>(y)*raw->pitch);
        return 0;
    } catch (...) { return 1; }
}
