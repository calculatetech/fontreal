struct LightSection {
    int first,last;
    double center,mass;
};

void restoreThinRuns(fontreal_v3::OutlineSamples &outline,const fontreal_v3::OutlineSamples &guide,
                     int turnFirst,int turnEnd,double gain,bool relaxed)
{
    using namespace fontreal_v3;
    const auto native=outline;
    const int width=4*outline.frame.width,height=4*outline.frame.height;
    const int pad=(outline.pitch-width)/2;
    for(const bool horizontal:{false,true}) {
        const int along=horizontal?width:height, normal=horizontal?height:width;
        const auto xy=[horizontal](int a,int n) {
            return horizontal ? std::pair{a,n}:std::pair{n,a};
        };
        const auto scan=[&](const OutlineSamples &source) {
            std::vector<std::vector<LightSection>> lines(along);
            for(int a=0;a<along;++a) {
                const auto at=[&](int n) {
                    const auto [x,y]=xy(a,n);
                    return source.highPixel(x,y)/255.;
                };
                for(int n=0;n<normal;) {
                    if(at(n)<.12) {
                        ++n;
                        continue;
                    }
                    const int first=n;
                    double mass=0,moment=0;
                    while(n<normal && at(n)>=.12) {
                        const auto weight=at(n);
                        mass+=weight;
                        moment+=(n+.5)*weight;
                        ++n;
                    }
                    lines[a].push_back({first,n,moment/mass,mass});
                }
            }
            return lines;
        };
        const auto from=scan(native),to=scan(guide);
        const auto match=[relaxed](const std::vector<LightSection> &line,const LightSection &s,double reach) {
            const int guard=relaxed ? 1 : 0;
            const LightSection *best=nullptr;
            for(const auto &t:line) {
                const double distance=std::abs(t.center-s.center);
                if(distance<reach && t.first<=s.last+guard && s.first<=t.last+guard) {
                    best=&t;
                    reach=distance;
                }
            }
            return best;
        };
        for(int a=2;a+2<along;++a) {
            for(const auto &s:from[a]) {
                const auto *reference=match(to[a],s,relaxed ? 2.63 : 1.38);
                if(!reference || s.mass<.68 || s.mass>3.62 || reference->mass>5.40
                        || s.mass>=.86*reference->mass)
                    continue;
                const auto *left=match(from[a-2],s,relaxed ? 2.18 : 1.80);
                const auto *right=match(from[a+2],s,relaxed ? 2.18 : 1.80);
                if(!left || !right || left->mass<.66 || right->mass<.66
                        || left->mass>5.10 || right->mass>5.10)
                    continue;
                const auto *guideLeft=match(to[a-2],*left,relaxed ? 2.63 : 1.48);
                const auto *guideRight=match(to[a+2],*right,relaxed ? 2.63 : 1.48);
                if(!guideLeft || !guideRight || guideLeft->mass<left->mass*(relaxed ? .96 : 1.04)
                        || guideRight->mass<right->mass*(relaxed ? .96 : 1.04))
                    continue;
                const double deficit=reference->mass-s.mass;
                const double expansion=std::min(1.10,gain*deficit);
                const double half=(s.mass+expansion)*.5;
                const double center=s.center+.20*std::clamp(reference->center-s.center,-1.1,1.1);
                for(int n=std::max(0,int(std::floor(center-half)));n<std::min(normal,int(std::ceil(center+half)));++n) {
                    const auto [x,y]=xy(a,n);
                    if(y/4>=turnFirst && y/4<turnEnd)
                        continue;
                    const double area=std::clamp(std::min(n+1.,center+half)-std::max(double(n),center-half),0.,1.);
                    auto &result=outline.pixels[(y+pad)*outline.pitch+x+pad];
                    result=std::max(result,Coverage(std::lround(255*area)));
                }
            }
        }
    }
    if((hasSeveralCounters(native,1) && !hasSeveralCounters(outline,1))
            || (hasSeveralCounters(native,2) && !hasSeveralCounters(outline,2)))
        outline=native;
}

void restoreWeakCrossings(fontreal_v3::OutlineSamples &outline,const fontreal_v3::OutlineSamples &guide)
{
    using namespace fontreal_v3;
    const auto source=outline;
    const int w=outline.frame.width,h=outline.frame.height;
    const int pad=(outline.pitch-4*w)/2;
    const bool oneCounter=hasSeveralCounters(source,1);
    const bool twoCounters=hasSeveralCounters(source,2);
    for(int y=std::max(2,int(.32*h)); y<std::min(h-2,int(.72*h)+1); ++y) {
        for(int x=0;x<w;) {
            if(guide.center(x,y)<15) {
                ++x;
                continue;
            }
            const int left=x++;
            while(x<w && guide.center(x,y)>=15)
                ++x;
            const int right=x;
            if(right-left<3 || right-left>5)
                continue;
            int total=0,missing=0,shared=0,weakCells=0;
            for(int n=left;n<right;++n) {
                const int a=source.center(n,y),b=guide.center(n,y);
                total+=b;
                missing+=std::max(0,b-a);
                shared+=std::min(a,b);
                weakCells+=b>=57 && a<.63*b;
            }
            if(total<240 || weakCells<2 || missing<.32*total || shared<.27*total)
                continue;
            const auto contact=[&](int border,int outsideRow) {
                int samples=0;
                for(int k=std::max(1,left*4-1);k<std::min(4*w-1,right*4+1);++k) {
                    const int continuation=std::min(guide.highPixel(k,border-1),guide.highPixel(k,border));
                    const int samePath=std::max({source.highPixel(k-1,outsideRow),
                                               source.highPixel(k,outsideRow),source.highPixel(k+1,outsideRow)});
                    samples+=std::min(continuation,samePath)>=45;
                }
                return samples>=2;
            };
            if(!contact(4*y,4*y-1) || !contact(4*(y+1),4*(y+1)))
                continue;
            const auto before=outline;
            for(int row=4*y;row<4*y+4;++row) {
                const double strength=(row%4==0 || row%4==3) ? .72 : .92;
                for(int k=left*4;k<right*4;++k) {
                    auto &value=outline.pixels[(row+pad)*outline.pitch+k+pad];
                    const auto fitted=std::lround(value+strength*(int(guide.highPixel(k,row))-value));
                    value=Coverage(fitted);
                }
            }
            if((oneCounter && !hasSeveralCounters(outline,1)) ||
               (twoCounters && !hasSeveralCounters(outline,2)))
                outline=before;
        }
    }
}

// A terminal has one inward continuation. An isolated mark has none.
double terminalSupport(const fontreal_v3::OutlineSamples &outline,int x,int y)
{
    const int width=outline.frame.width,height=outline.frame.height;
    const auto inside=[&](int px,int py) {return px>=0 && py>=0 && px<width && py<height;};
    const int coverage=outline.center(x,y);
    if(coverage<26 || coverage>163)
        return 0.;
    double dxSum=0,dySum=0,total=0,best=0;
    int inwardX=0,inwardY=0;
    for(int dy=-1;dy<=1;++dy) {
        for(int dx=-1;dx<=1;++dx) {
            const int px=x+dx,py=y+dy;
            if((!dx && !dy) || !inside(px,py) || !continuousInk(outline,x,y,dx,dy))
                continue;
            const int amount=outline.center(px,py);
            if(amount<38)
                continue;
            const double distance=std::hypot(dx,dy);
            dxSum+=amount*dx/distance;
            dySum+=amount*dy/distance;
            total+=amount;
            if(amount>best) {
                best=amount;
                inwardX=dx;
                inwardY=dy;
            }
        }
    }
    if(total==0. || best<100 || std::hypot(dxSum,dySum)<.77*total)
        return 0.;
    const int px=x+inwardX,py=y+inwardY;
    for(int dy=-1;dy<=1;++dy) {
        for(int dx=-1;dx<=1;++dx) {
            const int nx=px+dx,ny=py+dy;
            if(dx*inwardX+dy*inwardY<=0 || !inside(nx,ny))
                continue;
            if(outline.center(nx,ny)>=54 && continuousInk(outline,px,py,dx,dy))
                return .70;
        }
    }
    return 0.;
}
